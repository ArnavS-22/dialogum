"""
Unit tests for question_loader module.

Tests:
- Loading from file (JSON format)
- Format normalization
- Filtering by prop IDs and factors
- Proposition-factor pair expansion
"""

import json
import pytest
import tempfile
from pathlib import Path
from gum.clarification.question_loader import (
    load_flagged_propositions,
    filter_propositions,
    get_proposition_factor_pairs,
    _normalize_proposition_format,
    DEFAULT_FILE_PATH
)


class TestLoadFromFile:
    """Test loading flagged propositions from file."""
    
    @pytest.fixture
    def sample_propositions_file(self):
        """Create a temporary file with sample propositions."""
        data = {
            "propositions": [
                {
                    "prop_id": 1,
                    "prop_text": "Arnav values communication.",
                    "triggered_factors": ["inferred_intent", "opacity"],
                    "observations": [
                        {"id": 451, "observation_text": "User messaged contacts"}
                    ],
                    "prop_reasoning": "Based on messaging patterns"
                },
                {
                    "prop_id": 2,
                    "prop_text": "Arnav is focused on development.",
                    "triggered_factors": ["ambiguity"],
                    "observations": []
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(data, f)
            filepath = f.name
        
        yield filepath
        
        # Cleanup
        Path(filepath).unlink()
    
    @pytest.mark.asyncio
    async def test_load_from_file_success(self, sample_propositions_file):
        """Test successful loading from file."""
        props = await load_flagged_propositions(
            source="file",
            file_path=sample_propositions_file
        )
        
        assert len(props) == 2
        assert props[0]["prop_id"] == 1
        assert props[1]["prop_id"] == 2
        assert "inferred_intent" in props[0]["triggered_factors"]
    
    @pytest.mark.asyncio
    async def test_load_from_file_list_format(self):
        """Test loading when file contains a list directly."""
        data = [
            {
                "prop_id": 1,
                "prop_text": "Test proposition",
                "triggered_factors": ["inferred_intent"]
            }
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(data, f)
            filepath = f.name
        
        try:
            props = await load_flagged_propositions(source="file", file_path=filepath)
            assert len(props) == 1
            assert props[0]["prop_id"] == 1
        finally:
            Path(filepath).unlink()
    
    @pytest.mark.asyncio
    async def test_load_from_nonexistent_file(self):
        """Test error when file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            await load_flagged_propositions(
                source="file",
                file_path="/nonexistent/path/file.json"
            )
    
    @pytest.mark.asyncio
    async def test_load_from_invalid_json(self):
        """Test error when file contains invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            f.write("{ invalid json }")
            filepath = f.name
        
        try:
            with pytest.raises(json.JSONDecodeError):
                await load_flagged_propositions(source="file", file_path=filepath)
        finally:
            Path(filepath).unlink()


class TestNormalizePropositionFormat:
    """Test proposition format normalization."""
    
    def test_normalize_valid_proposition(self):
        """Test normalization of valid proposition."""
        prop = {
            "prop_id": 1,
            "prop_text": "Test proposition",
            "triggered_factors": ["inferred_intent", "opacity"],
            "observations": [{"id": 1, "observation_text": "Test"}],
            "prop_reasoning": "Some reasoning"
        }
        
        normalized = _normalize_proposition_format(prop)
        
        assert normalized is not None
        assert normalized["prop_id"] == 1
        assert normalized["prop_text"] == "Test proposition"
        assert "inferred_intent" in normalized["triggered_factors"]
        assert len(normalized["observations"]) == 1
    
    def test_normalize_alternative_field_names(self):
        """Test normalization with alternative field names."""
        prop = {
            "id": 1,  # Alternative to prop_id
            "text": "Test",  # Alternative to prop_text
            "triggered_factors": ["inferred_intent"]
        }
        
        normalized = _normalize_proposition_format(prop)
        
        assert normalized is not None
        assert normalized["prop_id"] == 1
        assert normalized["prop_text"] == "Test"
    
    def test_normalize_factor_ids_to_names(self):
        """Test conversion of factor IDs to names."""
        prop = {
            "prop_id": 1,
            "prop_text": "Test",
            "triggered_factors": [3, 6]  # Factor IDs instead of names
        }
        
        normalized = _normalize_proposition_format(prop)
        
        assert normalized is not None
        assert "inferred_intent" in normalized["triggered_factors"]
        assert "opacity" in normalized["triggered_factors"]
    
    def test_normalize_single_factor_string(self):
        """Test normalization when factor is a single string."""
        prop = {
            "prop_id": 1,
            "prop_text": "Test",
            "triggered_factors": "inferred_intent"  # Single string
        }
        
        normalized = _normalize_proposition_format(prop)
        
        assert normalized is not None
        assert isinstance(normalized["triggered_factors"], list)
        assert "inferred_intent" in normalized["triggered_factors"]
    
    def test_normalize_missing_required_fields(self):
        """Test that propositions missing required fields return None."""
        # Missing prop_id
        prop1 = {"prop_text": "Test"}
        assert _normalize_proposition_format(prop1) is None
        
        # Missing prop_text
        prop2 = {"prop_id": 1}
        assert _normalize_proposition_format(prop2) is None
    
    def test_normalize_no_valid_factors(self):
        """Test that propositions with no valid factors return None."""
        prop = {
            "prop_id": 1,
            "prop_text": "Test",
            "triggered_factors": ["invalid_factor", "another_invalid"]
        }
        
        normalized = _normalize_proposition_format(prop)
        assert normalized is None


class TestFilterPropositions:
    """Test proposition filtering."""
    
    @pytest.fixture
    def sample_propositions(self):
        """Sample propositions for filtering tests."""
        return [
            {
                "prop_id": 1,
                "prop_text": "Prop 1",
                "triggered_factors": ["inferred_intent", "opacity"],
                "observations": []
            },
            {
                "prop_id": 2,
                "prop_text": "Prop 2",
                "triggered_factors": ["ambiguity"],
                "observations": []
            },
            {
                "prop_id": 3,
                "prop_text": "Prop 3",
                "triggered_factors": ["inferred_intent", "privacy"],
                "observations": []
            }
        ]
    
    def test_filter_by_prop_ids(self, sample_propositions):
        """Test filtering by proposition IDs."""
        filtered = filter_propositions(sample_propositions, prop_ids=[1, 3])
        
        assert len(filtered) == 2
        assert filtered[0]["prop_id"] == 1
        assert filtered[1]["prop_id"] == 3
    
    def test_filter_by_factors(self, sample_propositions):
        """Test filtering by factor names."""
        filtered = filter_propositions(
            sample_propositions,
            factor_names=["inferred_intent"]
        )
        
        assert len(filtered) == 2  # Props 1 and 3 have inferred_intent
        assert all("inferred_intent" in p["triggered_factors"] for p in filtered)
    
    def test_filter_by_both_prop_ids_and_factors(self, sample_propositions):
        """Test filtering by both prop IDs and factors."""
        filtered = filter_propositions(
            sample_propositions,
            prop_ids=[1, 2],
            factor_names=["ambiguity"]
        )
        
        assert len(filtered) == 1  # Only prop 2 has ambiguity and is in [1, 2]
        assert filtered[0]["prop_id"] == 2
    
    def test_filter_no_filters(self, sample_propositions):
        """Test that no filters returns all propositions."""
        filtered = filter_propositions(sample_propositions)
        assert len(filtered) == len(sample_propositions)
    
    def test_filter_empty_result(self, sample_propositions):
        """Test filtering that results in empty list."""
        filtered = filter_propositions(
            sample_propositions,
            prop_ids=[999]  # Non-existent ID
        )
        assert len(filtered) == 0


class TestGetPropositionFactorPairs:
    """Test expansion of propositions into (prop, factor) pairs."""
    
    def test_get_proposition_factor_pairs(self):
        """Test expansion into pairs."""
        propositions = [
            {
                "prop_id": 1,
                "prop_text": "Prop 1",
                "triggered_factors": ["inferred_intent", "opacity"],
                "observations": []
            },
            {
                "prop_id": 2,
                "prop_text": "Prop 2",
                "triggered_factors": ["ambiguity"],
                "observations": []
            }
        ]
        
        pairs = get_proposition_factor_pairs(propositions)
        
        # Should have 3 pairs total: (1, inferred_intent), (1, opacity), (2, ambiguity)
        assert len(pairs) == 3
        
        # Check structure
        prop1, factor1 = pairs[0]
        assert prop1["prop_id"] == 1
        assert factor1 == "inferred_intent"
        
        prop2, factor2 = pairs[1]
        assert prop2["prop_id"] == 1
        assert factor2 == "opacity"
        
        prop3, factor3 = pairs[2]
        assert prop3["prop_id"] == 2
        assert factor3 == "ambiguity"
    
    def test_get_proposition_factor_pairs_empty(self):
        """Test with empty proposition list."""
        pairs = get_proposition_factor_pairs([])
        assert len(pairs) == 0
    
    def test_get_proposition_factor_pairs_no_factors(self):
        """Test with propositions that have no triggered factors."""
        propositions = [
            {
                "prop_id": 1,
                "prop_text": "Prop 1",
                "triggered_factors": [],
                "observations": []
            }
        ]
        
        pairs = get_proposition_factor_pairs(propositions)
        assert len(pairs) == 0


class TestLoadFromFileInvariants:
    """Test invariants for file loading."""
    
    @pytest.mark.asyncio
    async def test_load_invalid_source(self):
        """Test error on invalid source parameter."""
        with pytest.raises(ValueError, match="Invalid source"):
            await load_flagged_propositions(source="invalid")
    
    @pytest.mark.asyncio
    async def test_load_db_without_session(self):
        """Test error when loading from DB without session."""
        with pytest.raises(ValueError, match="db_session required"):
            await load_flagged_propositions(source="db")
    
    @pytest.mark.asyncio
    async def test_loaded_propositions_have_required_fields(self, sample_propositions_file):
        """Test that all loaded propositions have required fields."""
        props = await load_flagged_propositions(
            source="file",
            file_path=sample_propositions_file
        )
        
        for prop in props:
            assert "prop_id" in prop
            assert "prop_text" in prop
            assert "triggered_factors" in prop
            assert "observations" in prop
            assert isinstance(prop["triggered_factors"], list)
            assert isinstance(prop["observations"], list)


class TestFilePathHandling:
    """Test file path handling."""
    
    @pytest.mark.asyncio
    async def test_default_file_path(self):
        """Test that default file path is used when none provided."""
        # This will fail if file doesn't exist, which is expected
        # We're just testing that it tries to use the default path
        try:
            await load_flagged_propositions(source="file")
        except FileNotFoundError as e:
            # Should mention the default path in error
            assert DEFAULT_FILE_PATH in str(e)

