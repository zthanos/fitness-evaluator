"""Runtime Comparison Report for Side-by-Side CE vs Legacy evaluation.

Provides a structured report format for comparing CE and legacy runtime
results, and a helper to run both runtimes and produce the report.

Requirements: 6.2 (Side-by-Side Comparison)
"""
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class RuntimeResult:
    """Captured result from a single runtime execution."""

    runtime: str
    content: str
    latency_ms: float
    tool_calls_made: int
    iterations: int
    context_token_count: int
    ce_context_used: bool
    error: Optional[str] = None

    @staticmethod
    def from_response(response: Dict[str, Any]) -> "RuntimeResult":
        return RuntimeResult(
            runtime=response.get("runtime", "unknown"),
            content=response.get("content", ""),
            latency_ms=response.get("latency_ms", 0.0),
            tool_calls_made=response.get("tool_calls_made", 0),
            iterations=response.get("iterations", 0),
            context_token_count=response.get("context_token_count", 0),
            ce_context_used=response.get("ce_context_used", False),
        )

    @staticmethod
    def from_error(runtime: str, error: Exception) -> "RuntimeResult":
        return RuntimeResult(
            runtime=runtime,
            content="",
            latency_ms=0.0,
            tool_calls_made=0,
            iterations=0,
            context_token_count=0,
            ce_context_used=runtime == "ce",
            error=str(error),
        )


@dataclass
class ComparisonReport:
    """Structured comparison of CE vs legacy runtime results.

    Captures latency, token usage, tool call, and content differences
    between the two runtimes for a single user message.
    """

    timestamp: str
    user_message: str
    user_id: int
    session_id: int

    # Individual results
    ce_result: Optional[RuntimeResult] = None
    legacy_result: Optional[RuntimeResult] = None

    # Computed differences
    latency_diff_ms: float = 0.0
    token_diff: int = 0
    tool_calls_diff: int = 0
    iterations_diff: int = 0
    content_length_diff: int = 0
    both_succeeded: bool = False
    ce_faster: bool = False

    def compute_diffs(self) -> None:
        """Populate the diff fields from the two results."""
        ce = self.ce_result
        legacy = self.legacy_result

        if ce is None or legacy is None:
            return

        self.both_succeeded = ce.error is None and legacy.error is None
        self.latency_diff_ms = ce.latency_ms - legacy.latency_ms
        self.token_diff = ce.context_token_count - legacy.context_token_count
        self.tool_calls_diff = ce.tool_calls_made - legacy.tool_calls_made
        self.iterations_diff = ce.iterations - legacy.iterations
        self.content_length_diff = len(ce.content) - len(legacy.content)
        self.ce_faster = ce.latency_ms < legacy.latency_ms

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the report to a plain dict (JSON-friendly)."""
        data: Dict[str, Any] = {
            "timestamp": self.timestamp,
            "user_message": self.user_message,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "latency_diff_ms": self.latency_diff_ms,
            "token_diff": self.token_diff,
            "tool_calls_diff": self.tool_calls_diff,
            "iterations_diff": self.iterations_diff,
            "content_length_diff": self.content_length_diff,
            "both_succeeded": self.both_succeeded,
            "ce_faster": self.ce_faster,
        }
        if self.ce_result is not None:
            data["ce"] = asdict(self.ce_result)
        if self.legacy_result is not None:
            data["legacy"] = asdict(self.legacy_result)
        return data

    def summary(self) -> str:
        """Return a human-readable one-line summary."""
        if not self.both_succeeded:
            failed = []
            if self.ce_result and self.ce_result.error:
                failed.append("ce")
            if self.legacy_result and self.legacy_result.error:
                failed.append("legacy")
            return f"comparison incomplete – failed runtimes: {', '.join(failed)}"

        faster = "ce" if self.ce_faster else "legacy"
        return (
            f"latency_diff={self.latency_diff_ms:+.0f}ms "
            f"token_diff={self.token_diff:+d} "
            f"tool_calls_diff={self.tool_calls_diff:+d} "
            f"content_len_diff={self.content_length_diff:+d} "
            f"faster={faster}"
        )


async def run_comparison(
    *,
    user_message: str,
    session_id: int,
    user_id: int,
    ce_handler_fn,
    legacy_handler_fn,
    invocation_logger=None,
) -> ComparisonReport:
    """Execute both runtimes and produce a ``ComparisonReport``.

    Each handler function should be an async callable that accepts
    ``(user_message: str)`` and returns the standard response dict.

    Errors in either runtime are captured in the report rather than
    propagated, so the caller always gets a complete report.

    Args:
        user_message: The athlete's message.
        session_id: Active session id.
        user_id: Athlete / user id.
        ce_handler_fn: Async callable for the CE runtime path.
        legacy_handler_fn: Async callable for the legacy runtime path.
        invocation_logger: Optional ``InvocationLogger`` for telemetry.

    Returns:
        A fully populated ``ComparisonReport``.
    """
    report = ComparisonReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        user_message=user_message,
        user_id=user_id,
        session_id=session_id,
    )

    # Run CE path
    try:
        ce_response = await ce_handler_fn(user_message)
        report.ce_result = RuntimeResult.from_response(ce_response)
    except Exception as exc:
        logger.warning("CE runtime failed during comparison: %s", exc)
        report.ce_result = RuntimeResult.from_error("ce", exc)

    # Run legacy path
    try:
        legacy_response = await legacy_handler_fn(user_message)
        report.legacy_result = RuntimeResult.from_response(legacy_response)
    except Exception as exc:
        logger.warning("Legacy runtime failed during comparison: %s", exc)
        report.legacy_result = RuntimeResult.from_error("legacy", exc)

    report.compute_diffs()

    logger.info(
        "Runtime comparison complete: %s",
        report.summary(),
        extra={
            "user_id": user_id,
            "session_id": session_id,
            "both_succeeded": report.both_succeeded,
            "latency_diff_ms": report.latency_diff_ms,
        },
    )

    # Persist to telemetry if logger provided
    if invocation_logger is not None:
        _log_comparison_telemetry(invocation_logger, report)

    return report


def _log_comparison_telemetry(invocation_logger, report: ComparisonReport) -> None:
    """Write a comparison telemetry record via the InvocationLogger."""
    from app.ai.telemetry.invocation_logger import InvocationLog

    invocation_logger.log(
        InvocationLog(
            timestamp=report.timestamp,
            operation_type="runtime_comparison",
            athlete_id=report.user_id,
            model_used="comparison",
            context_token_count=report.ce_result.context_token_count if report.ce_result else 0,
            response_token_count=0,
            latency_ms=max(
                (report.ce_result.latency_ms if report.ce_result else 0),
                (report.legacy_result.latency_ms if report.legacy_result else 0),
            ),
            success_status=report.both_succeeded,
            error_message=None if report.both_succeeded else report.summary(),
            retrieval_latency_ms=report.latency_diff_ms,
            model_latency_ms=None,
            total_latency_ms=(
                (report.ce_result.latency_ms if report.ce_result else 0)
                + (report.legacy_result.latency_ms if report.legacy_result else 0)
            ),
            fallback_used=False,
        )
    )
