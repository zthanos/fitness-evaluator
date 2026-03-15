"""Tests for domain knowledge serialization.

Validates that TrainingZone, DomainKnowledge, and DomainKnowledgeLoader
produce JSON-serializable output, and that ChatContextBuilder can count
tokens for domain knowledge without errors.
"""

import json
import pytest
from unittest.mock import MagicMock

from app.ai.config.domain_loader import (
    DomainKnowledge,
    DomainKnowledgeLoader,
    TrainingZone,
)
from app.ai.context.chat_context import ChatContextBuilder


# --- TrainingZone serialization ---

class TestTrainingZoneSerialization:
    def test_to_dict_returns_serializable(self):
        zone = TrainingZone(
            name="z1_recovery",
            hr_pct_max=(50, 60),
            rpe=(1, 2),
            description="Active recovery"
        )
        d = zone.to_dict()
        # Must be JSON-serializable
        json_str = json.dumps(d)
        assert '"name": "z1_recovery"' in json_str

    def test_to_dict_converts_tuples_to_lists(self):
        zone = TrainingZone(name="z2", hr_pct_max=(60, 70), rpe=(3, 4), description="Aerobic")
        d = zone.to_dict()
        assert isinstance(d['hr_pct_max'], list)
        assert isinstance(d['rpe'], list)
        assert d['hr_pct_max'] == [60, 70]
        assert d['rpe'] == [3, 4]

    def test_to_dict_preserves_all_fields(self):
        zone = TrainingZone(name="z5", hr_pct_max=(90, 100), rpe=(9, 10), description="VO2 max")
        d = zone.to_dict()
        assert set(d.keys()) == {'name', 'hr_pct_max', 'rpe', 'description'}


# --- DomainKnowledge serialization ---

class TestDomainKnowledgeSerialization:
    def _make_domain_knowledge(self):
        zones = {
            "z1": TrainingZone("z1", (50, 60), (1, 2), "Recovery"),
            "z2": TrainingZone("z2", (60, 70), (3, 4), "Aerobic"),
        }
        return DomainKnowledge(
            training_zones=zones,
            effort_levels={"easy": {"zones": ["z1"], "target_pct": 80}},
            recovery_guidelines={"rest_days_per_week": 1, "max_consecutive_training_days": 6,
                                 "hard_sessions_per_week": 2, "recovery_week_frequency": 4},
            nutrition_targets={"protein_g_per_kg": [1.6, 2.2], "carbs_pct_calories": [45, 65],
                               "fat_pct_calories": [20, 35]},
        )

    def test_to_dict_is_json_serializable(self):
        dk = self._make_domain_knowledge()
        d = dk.to_dict()
        json_str = json.dumps(d, indent=2)
        assert "z1" in json_str
        assert "Recovery" in json_str

    def test_to_dict_converts_nested_training_zones(self):
        dk = self._make_domain_knowledge()
        d = dk.to_dict()
        assert isinstance(d['training_zones']['z1'], dict)
        assert d['training_zones']['z1']['hr_pct_max'] == [50, 60]

    def test_to_dict_preserves_plain_dict_fields(self):
        dk = self._make_domain_knowledge()
        d = dk.to_dict()
        assert d['effort_levels'] == {"easy": {"zones": ["z1"], "target_pct": 80}}
        assert d['recovery_guidelines']['rest_days_per_week'] == 1
        assert d['nutrition_targets']['protein_g_per_kg'] == [1.6, 2.2]


# --- DomainKnowledgeLoader dict conversion ---

class TestDomainKnowledgeLoaderDictConversion:
    def test_load_as_dict_returns_serializable(self):
        loader = DomainKnowledgeLoader()
        d = loader.load_as_dict()
        json_str = json.dumps(d, indent=2)
        assert "training_zones" in json_str

    def test_load_as_dict_matches_load_to_dict(self):
        loader = DomainKnowledgeLoader()
        dk = loader.load()
        assert loader.load_as_dict() == dk.to_dict()


# --- ChatContextBuilder token counting with domain knowledge ---

class TestChatContextBuilderDomainKnowledge:
    def test_count_dict_tokens_with_plain_dict(self):
        mock_db = MagicMock()
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        data = {"key": "value", "nested": {"a": 1}}
        tokens = builder._count_dict_tokens(data)
        assert tokens > 0

    def test_count_dict_tokens_with_dataclass_values(self):
        """The core bug scenario: dict containing TrainingZone dataclass objects."""
        mock_db = MagicMock()
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        zone = TrainingZone("z1", (50, 60), (1, 2), "Recovery")
        data = {"training_zones": {"z1": zone}}
        # This should NOT raise TypeError
        tokens = builder._count_dict_tokens(data)
        assert tokens > 0

    def test_count_dict_tokens_with_domain_knowledge_to_dict(self):
        """Using to_dict() output should work seamlessly."""
        mock_db = MagicMock()
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        loader = DomainKnowledgeLoader()
        dk = loader.load()
        tokens = builder._count_dict_tokens(dk.to_dict())
        assert tokens > 0

    def test_add_domain_knowledge_with_real_data(self):
        """End-to-end: load domain knowledge and add to context builder."""
        mock_db = MagicMock()
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        loader = DomainKnowledgeLoader()
        dk = loader.load()
        builder.add_domain_knowledge(dk.to_dict())
        layer_tokens = builder.get_layer_tokens()
        assert layer_tokens["domain_knowledge"] > 0

    def test_count_dict_tokens_empty_dict(self):
        mock_db = MagicMock()
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        assert builder._count_dict_tokens({}) == 0

    def test_count_dict_tokens_with_mixed_nested_types(self):
        """Dict with lists, nested dicts, and dataclass objects."""
        mock_db = MagicMock()
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        zone = TrainingZone("z3", (70, 80), (5, 6), "Tempo")
        data = {
            "zones": [zone],
            "plain": {"a": 1},
            "list_of_dicts": [{"x": 10}],
            "tuple_val": (1, 2, 3),
        }
        tokens = builder._count_dict_tokens(data)
        assert tokens > 0
