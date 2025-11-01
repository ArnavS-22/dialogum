"""
Unit tests for question_config module.

Tests:
- Factor ID to method mapping
- Factor name lookups
- Factor description retrieval
- Validation functions
- Error handling for invalid inputs
"""

import pytest
from gum.clarification.question_config import (
    get_method_for_factor,
    get_factor_name,
    get_factor_description,
    get_factor_id_from_name,
    validate_factor_id,
    get_all_factor_ids,
    get_few_shot_factor_ids,
    get_controlled_qg_factor_ids,
    FACTOR_METHOD_MAP,
    FACTOR_NAMES,
    FACTOR_DESCRIPTIONS
)


class TestFactorMappings:
    """Test factor mapping functions."""
    
    def test_get_method_for_factor_valid(self):
        """Test getting method for valid factor IDs."""
        assert get_method_for_factor(1) == "controlled_qg"
        assert get_method_for_factor(3) == "few_shot"
        assert get_method_for_factor(6) == "few_shot"
        assert get_method_for_factor(8) == "few_shot"
        assert get_method_for_factor(11) == "few_shot"
        assert get_method_for_factor(12) == "controlled_qg"
    
    def test_get_method_for_factor_invalid(self):
        """Test error on invalid factor ID."""
        with pytest.raises(ValueError, match="Invalid factor_id"):
            get_method_for_factor(0)
        
        with pytest.raises(ValueError, match="Invalid factor_id"):
            get_method_for_factor(13)
        
        with pytest.raises(ValueError, match="Invalid factor_id"):
            get_method_for_factor(-1)
    
    def test_get_factor_name_valid(self):
        """Test getting factor names."""
        assert get_factor_name(1) == "identity_mismatch"
        assert get_factor_name(3) == "inferred_intent"
        assert get_factor_name(6) == "opacity"
        assert get_factor_name(11) == "ambiguity"
    
    def test_get_factor_name_invalid(self):
        """Test error on invalid factor ID."""
        with pytest.raises(ValueError, match="Invalid factor_id"):
            get_factor_name(0)
    
    def test_get_factor_description_valid(self):
        """Test getting factor descriptions."""
        desc = get_factor_description(1)
        assert "Identity Mismatch" in desc
        assert "personality trait" in desc
        
        desc = get_factor_description(3)
        assert "Inferred Intent" in desc
        assert "WHY" in desc
    
    def test_get_factor_description_invalid(self):
        """Test error on invalid factor ID."""
        with pytest.raises(ValueError, match="Invalid factor_id"):
            get_factor_description(100)
    
    def test_get_factor_id_from_name_valid(self):
        """Test reverse lookup from name to ID."""
        assert get_factor_id_from_name("identity_mismatch") == 1
        assert get_factor_id_from_name("inferred_intent") == 3
        assert get_factor_id_from_name("opacity") == 6
        assert get_factor_id_from_name("ambiguity") == 11
    
    def test_get_factor_id_from_name_invalid(self):
        """Test None return for invalid name."""
        assert get_factor_id_from_name("invalid_factor") is None
        assert get_factor_id_from_name("") is None
    
    def test_validate_factor_id(self):
        """Test factor ID validation."""
        assert validate_factor_id(1) is True
        assert validate_factor_id(12) is True
        assert validate_factor_id(0) is False
        assert validate_factor_id(13) is False
        assert validate_factor_id(-1) is False


class TestFactorLists:
    """Test functions that return lists of factors."""
    
    def test_get_all_factor_ids(self):
        """Test getting all factor IDs."""
        all_ids = get_all_factor_ids()
        assert len(all_ids) == 12
        assert set(all_ids) == set(range(1, 13))
    
    def test_get_few_shot_factor_ids(self):
        """Test getting few-shot factor IDs."""
        few_shot_ids = get_few_shot_factor_ids()
        # Factors 3, 6, 8, 11 use few-shot
        assert set(few_shot_ids) == {3, 6, 8, 11}
    
    def test_get_controlled_qg_factor_ids(self):
        """Test getting controlled QG factor IDs."""
        controlled_ids = get_controlled_qg_factor_ids()
        # 8 factors use controlled QG
        assert len(controlled_ids) == 8
        assert set(controlled_ids) == {1, 2, 4, 5, 7, 9, 10, 12}


class TestDataIntegrity:
    """Test integrity of configuration data."""
    
    def test_all_factors_have_method(self):
        """Test that all 12 factors have a method mapping."""
        assert len(FACTOR_METHOD_MAP) == 12
        for i in range(1, 13):
            assert i in FACTOR_METHOD_MAP
    
    def test_all_factors_have_name(self):
        """Test that all 12 factors have a name."""
        assert len(FACTOR_NAMES) == 12
        for i in range(1, 13):
            assert i in FACTOR_NAMES
    
    def test_all_factors_have_description(self):
        """Test that all 12 factors have a description."""
        assert len(FACTOR_DESCRIPTIONS) == 12
        for i in range(1, 13):
            assert i in FACTOR_DESCRIPTIONS
    
    def test_factor_names_unique(self):
        """Test that factor names are unique."""
        names = list(FACTOR_NAMES.values())
        assert len(names) == len(set(names))
    
    def test_methods_valid(self):
        """Test that all methods are either few_shot or controlled_qg."""
        valid_methods = {"few_shot", "controlled_qg"}
        for method in FACTOR_METHOD_MAP.values():
            assert method in valid_methods


class TestConstants:
    """Test that constants are defined and reasonable."""
    
    def test_constants_exist(self):
        """Test that validation constants are defined."""
        from gum.clarification.question_config import (
            MAX_REASONING_WORDS,
            HARD_REASONING_LIMIT,
            MIN_QUESTION_LENGTH,
            MAX_QUESTION_LENGTH,
            MAX_GENERATION_RETRIES,
            MAX_EVIDENCE_ITEMS
        )
        
        assert MAX_REASONING_WORDS > 0
        assert HARD_REASONING_LIMIT > MAX_REASONING_WORDS
        assert MIN_QUESTION_LENGTH > 0
        assert MAX_QUESTION_LENGTH > MIN_QUESTION_LENGTH
        assert MAX_GENERATION_RETRIES >= 0
        assert MAX_EVIDENCE_ITEMS > 0

