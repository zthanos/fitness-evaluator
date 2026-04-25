"""In-memory request metrics and log capture for the telemetry page."""
import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RequestRecord:
    timestamp: float
    method: str
    path: str
    status_code: int
    duration_ms: float


@dataclass
class LogRecord:
    timestamp: float
    level: str
    logger_name: str
    message: str


class _LogHandler(logging.Handler):
    def __init__(self, store: deque):
        super().__init__()
        self._store = store

    def emit(self, record: logging.LogRecord):
        try:
            self._store.append(LogRecord(
                timestamp=record.created,
                level=record.levelname,
                logger_name=record.name,
                message=self.format(record),
            ))
        except Exception:
            pass


_UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.I)
_NUMERIC = re.compile(r'/\d+')


def _normalize(path: str) -> str:
    path = _UUID.sub(':id', path)
    path = _NUMERIC.sub('/:id', path)
    return path


def _percentile(sorted_data: list, p: float) -> float:
    if not sorted_data:
        return 0.0
    idx = max(0, int(p / 100 * (len(sorted_data) - 1)))
    return round(sorted_data[idx], 1)


class MetricsCollector:
    """Singleton in-memory store for request metrics and recent logs."""

    _instance: Optional['MetricsCollector'] = None

    def __new__(cls):
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._requests: deque[RequestRecord] = deque(maxlen=10_000)
            inst._logs: deque[LogRecord] = deque(maxlen=500)
            inst._start_time = time.time()
            handler = _LogHandler(inst._logs)
            handler.setLevel(logging.WARNING)
            handler.setFormatter(logging.Formatter('%(message)s'))
            logging.root.addHandler(handler)
            cls._instance = inst
        return cls._instance

    def record(self, method: str, path: str, status_code: int, duration_ms: float):
        self._requests.append(RequestRecord(
            timestamp=time.time(),
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
        ))

    @property
    def uptime_seconds(self) -> int:
        return int(time.time() - self._start_time)

    def get_stats(self, window_seconds: int = 3600) -> dict:
        cutoff = time.time() - window_seconds
        records = [r for r in self._requests if r.timestamp >= cutoff]

        if not records:
            return {
                'window_seconds': window_seconds,
                'total_requests': 0,
                'rps': 0.0,
                'success_rate': 100.0,
                'error_rate': 0.0,
                'latency': {'p50': 0, 'p95': 0, 'p99': 0, 'avg': 0},
                'status_codes': {},
                'top_endpoints': [],
                'recent_errors': [],
                'uptime_seconds': self.uptime_seconds,
            }

        durations_sorted = sorted(r.duration_ms for r in records)
        errors = [r for r in records if r.status_code >= 400]

        # Per-path aggregation
        path_map: dict = {}
        for r in records:
            key = _normalize(r.path)
            if key not in path_map:
                path_map[key] = {'count': 0, 'errors': 0, 'durations': []}
            path_map[key]['count'] += 1
            if r.status_code >= 400:
                path_map[key]['errors'] += 1
            path_map[key]['durations'].append(r.duration_ms)

        top_endpoints = sorted(
            [
                {
                    'path': p,
                    'count': s['count'],
                    'error_rate': round(s['errors'] / s['count'] * 100, 1),
                    'p95_ms': _percentile(sorted(s['durations']), 95),
                    'avg_ms': round(sum(s['durations']) / len(s['durations']), 1),
                }
                for p, s in path_map.items()
            ],
            key=lambda x: x['count'],
            reverse=True,
        )[:10]

        # Status code counts
        status_counts: dict = {}
        for r in records:
            k = str(r.status_code)
            status_counts[k] = status_counts.get(k, 0) + 1

        recent_errors = [
            {
                'timestamp': r.timestamp,
                'method': r.method,
                'path': r.path,
                'status': r.status_code,
                'duration_ms': round(r.duration_ms, 1),
            }
            for r in reversed(list(self._requests))
            if r.status_code >= 400
        ][:20]

        last_minute = [r for r in records if r.timestamp >= time.time() - 60]
        rps = round(len(last_minute) / 60, 3)
        n = len(records)

        return {
            'window_seconds': window_seconds,
            'total_requests': n,
            'rps': rps,
            'success_rate': round((n - len(errors)) / n * 100, 2),
            'error_rate': round(len(errors) / n * 100, 2),
            'latency': {
                'p50': _percentile(durations_sorted, 50),
                'p95': _percentile(durations_sorted, 95),
                'p99': _percentile(durations_sorted, 99),
                'avg': round(sum(durations_sorted) / n, 1),
            },
            'status_codes': status_counts,
            'top_endpoints': top_endpoints,
            'recent_errors': recent_errors,
            'uptime_seconds': self.uptime_seconds,
        }

    def get_logs(self, level: Optional[str] = None, limit: int = 50) -> List[dict]:
        logs = list(reversed(list(self._logs)))
        if level:
            logs = [l for l in logs if l.level == level.upper()]
        return [
            {
                'timestamp': l.timestamp,
                'level': l.level,
                'logger': l.logger_name,
                'message': l.message,
            }
            for l in logs[:limit]
        ]


# Module-level singleton — import this everywhere
metrics = MetricsCollector()
