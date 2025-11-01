"""
Unit tests for question_prompts module.

Tests:
- Few-shot example retrieval
- Prompt building (few-shot and controlled QG)
- Observation formatting
- Example formatting
"""

import pytest
from gum.clarification.question_prompts import (
    get_few_shot_examples,
    format_few_shot_examples,
    build_few_shot_prompt,
    build_controlled_qg_prompt,
    format_observation_summary,
    FEW_SHOT_EXAMPLES
)


class TestFewShotExamples:
    """Test few-shot example retrieval."""
    
    def test_get_few_shot_examples_valid(self):
        """Test retrieving examples for few-shot factors."""
        # Factors 3, 6, 8, 11 use few-shot
        for factor_id in [3, 6, 8, 11]:
            examples = get_few_shot_examples(factor_id)
            assert isinstance(examples, list)
            assert len(examples) >= 2  # At least 2 examples per factor
            
            for ex in examples:
                assert "prop" in ex
                assert "question" in ex
                assert "reasoning" in ex
                assert "evidence" in ex
    
    def test_get_few_shot_examples_invalid(self):
        """Test error for controlled QG factors."""
        # Factor 1 uses controlled QG, not few-shot
        with pytest.raises(ValueError, match="does not use few-shot"):
            get_few_shot_examples(1)
    
    def test_few_shot_examples_structure(self):
        """Test that all few-shot examples have required fields."""
        for factor_id, examples in FEW_SHOT_EXAMPLES.items():
            for i, ex in enumerate(examples):
                assert "prop" in ex, f"Factor {factor_id} example {i} missing 'prop'"
                assert "question" in ex, f"Factor {factor_id} example {i} missing 'question'"
                assert "reasoning" in ex, f"Factor {factor_id} example {i} missing 'reasoning'"
                assert "evidence" in ex, f"Factor {factor_id} example {i} missing 'evidence'"
                
                # Check types
                assert isinstance(ex["prop"], str)
                assert isinstance(ex["question"], str)
                assert isinstance(ex["reasoning"], str)
                assert isinstance(ex["evidence"], list)


class TestFormatFewShotExamples:
    """Test few-shot example formatting."""
    
    def test_format_few_shot_examples(self):
        """Test formatting examples as string."""
        formatted = format_few_shot_examples(3)  # Inferred Intent
        
        assert isinstance(formatted, str)
        assert "Example 1:" in formatted
        assert "Proposition:" in formatted
        assert "Question:" in formatted
        assert "Reasoning:" in formatted
    
    def test_format_includes_all_examples(self):
        """Test that formatting includes all examples."""
        factor_id = 3
        examples = get_few_shot_examples(factor_id)
        formatted = format_few_shot_examples(factor_id)
        
        # Should have as many "Example N:" as there are examples
        example_count = formatted.count("Example ")
        assert example_count == len(examples)
    
    def test_format_includes_evidence_when_present(self):
        """Test that evidence is included when available."""
        formatted = format_few_shot_examples(3)  # Has evidence
        assert "Evidence:" in formatted or "obs_" in formatted


class TestBuildFewShotPrompt:
    """Test few-shot prompt building."""
    
    def test_build_few_shot_prompt_structure(self):
        """Test that prompt has correct structure."""
        prop_text = "Arnav values communication with friends."
        factor_id = 3  # Inferred Intent
        obs_summary = "obs_1: some observation"
        
        system_prompt, user_prompt = build_few_shot_prompt(
            prop_text, factor_id, obs_summary
        )
        
        assert isinstance(system_prompt, str)
        assert isinstance(user_prompt, str)
        
        # Check system prompt contains key elements
        assert "examples" in system_prompt.lower()
        assert prop_text in system_prompt
        assert obs_summary in system_prompt
        assert "Inferred Intent" in system_prompt
        
        # Check user prompt asks for JSON
        assert "JSON" in user_prompt or "json" in user_prompt
        assert "question" in user_prompt
        assert "reasoning" in user_prompt
    
    def test_build_few_shot_prompt_includes_examples(self):
        """Test that prompt includes example questions."""
        prop_text = "Test proposition"
        factor_id = 6  # Opacity
        obs_summary = ""
        
        system_prompt, user_prompt = build_few_shot_prompt(
            prop_text, factor_id, obs_summary
        )
        
        # Should include formatted examples
        assert "Example" in system_prompt
        examples = get_few_shot_examples(factor_id)
        # Check that at least one example question appears
        assert any(ex["question"] in system_prompt for ex in examples)


class TestBuildControlledQGPrompt:
    """Test controlled QG prompt building."""
    
    def test_build_controlled_qg_prompt_structure(self):
        """Test that prompt has correct structure."""
        prop_text = "Arnav is an exceptional problem solver."
        factor_id = 1  # Identity Mismatch
        obs_summary = "obs_1: solved complex coding challenge"
        
        system_prompt, user_prompt = build_controlled_qg_prompt(
            prop_text, factor_id, obs_summary
        )
        
        assert isinstance(system_prompt, str)
        assert isinstance(user_prompt, str)
        
        # Check system prompt contains key elements
        assert "clarifying question" in system_prompt.lower()
        assert prop_text in system_prompt
        assert obs_summary in system_prompt
        assert "Identity Mismatch" in system_prompt
        
        # Check guidelines are present
        assert "Guidelines:" in system_prompt or "polite" in system_prompt.lower()
        
        # Check user prompt asks for JSON
        assert "JSON" in user_prompt or "json" in user_prompt
    
    def test_build_controlled_qg_prompt_with_validation_feedback(self):
        """Test prompt with validation feedback for retry."""
        prop_text = "Test proposition"
        factor_id = 5  # Over-Positive
        obs_summary = ""
        feedback = "Question was too leading. Use softer language."
        
        system_prompt, user_prompt = build_controlled_qg_prompt(
            prop_text, factor_id, obs_summary, feedback
        )
        
        # Should include feedback
        assert feedback in system_prompt
        assert "failed validation" in system_prompt.lower() or "correct" in system_prompt.lower()
    
    def test_build_controlled_qg_prompt_all_factors(self):
        """Test prompt building for all controlled QG factors."""
        # Factors that use controlled QG
        controlled_factors = [1, 2, 4, 5, 7, 9, 10, 12]
        
        for factor_id in controlled_factors:
            system_prompt, user_prompt = build_controlled_qg_prompt(
                "Test proposition", factor_id, "Test observations"
            )
            
            assert system_prompt is not None
            assert len(system_prompt) > 100  # Should have substantial content
            assert user_prompt is not None


class TestFormatObservationSummary:
    """Test observation summary formatting."""
    
    def test_format_observation_summary_dict_format(self):
        """Test formatting observations as dicts."""
        observations = [
            {"id": 451, "observation_text": "User opened multiple chat windows"},
            {"id": 452, "observation_text": "User messaged 3 contacts"}
        ]
        
        summary = format_observation_summary(observations)
        
        assert isinstance(summary, str)
        assert "obs_451" in summary
        assert "obs_452" in summary
        assert "chat windows" in summary
    
    def test_format_observation_summary_object_format(self):
        """Test formatting observations as objects."""
        class MockObservation:
            def __init__(self, obs_id, text):
                self.id = obs_id
                self.observation_text = text
        
        observations = [
            MockObservation(451, "User opened multiple chat windows"),
            MockObservation(452, "User messaged 3 contacts")
        ]
        
        summary = format_observation_summary(observations)
        
        assert "obs_451" in summary
        assert "obs_452" in summary
    
    def test_format_observation_summary_empty(self):
        """Test formatting empty observation list."""
        summary = format_observation_summary([])
        assert isinstance(summary, str)
        assert "No specific observations" in summary or summary == ""
    
    def test_format_observation_summary_truncates_long_text(self):
        """Test that long observations are truncated."""
        long_text = "x" * 200  # 200 characters
        observations = [
            {"id": 1, "observation_text": long_text}
        ]
        
        summary = format_observation_summary(observations)
        
        # Should be truncated with ellipsis
        assert "..." in summary
        assert len(summary) < len(long_text) + 50  # Much shorter than original
    
    def test_format_observation_summary_respects_max_obs(self):
        """Test that only max_obs observations are included."""
        observations = [{"id": i, "observation_text": f"Obs {i}"} for i in range(10)]
        
        summary = format_observation_summary(observations, max_obs=3)
        
        # Should only include first 3
        assert "obs_0" in summary
        assert "obs_1" in summary
        assert "obs_2" in summary
        
        # Should indicate more exist
        assert "more" in summary.lower() or "..." in summary


class TestPromptInvariants:
    """Test invariants that should hold for all prompts."""
    
    def test_all_prompts_request_json(self):
        """Test that all prompts request JSON output."""
        # Test few-shot
        for factor_id in [3, 6, 8, 11]:
            _, user_prompt = build_few_shot_prompt("Test", factor_id, "")
            assert "json" in user_prompt.lower()
        
        # Test controlled QG
        for factor_id in [1, 2, 4, 5, 7, 9, 10, 12]:
            _, user_prompt = build_controlled_qg_prompt("Test", factor_id, "")
            assert "json" in user_prompt.lower()
    
    def test_all_prompts_include_factor_description(self):
        """Test that all prompts include factor description."""
        # Test few-shot
        for factor_id in [3, 6, 8, 11]:
            system_prompt, _ = build_few_shot_prompt("Test", factor_id, "")
            from gum.clarification.question_config import get_factor_name
            factor_name = get_factor_name(factor_id)
            # Should mention the factor somehow
            assert factor_name.replace("_", " ").lower() in system_prompt.lower() or \
                   any(word in system_prompt for word in factor_name.split("_"))
        
        # Test controlled QG
        for factor_id in [1, 2, 4, 5, 7, 9, 10, 12]:
            system_prompt, _ = build_controlled_qg_prompt("Test", factor_id, "")
            # Should include factor description
            assert len(system_prompt) > 200  # Substantial content
    
    def test_prompts_include_proposition_text(self):
        """Test that prompts always include the proposition being questioned."""
        prop_text = "This is a unique test proposition XYZ123"
        
        # Test few-shot
        system_prompt, _ = build_few_shot_prompt(prop_text, 3, "")
        assert prop_text in system_prompt
        
        # Test controlled QG
        system_prompt, _ = build_controlled_qg_prompt(prop_text, 1, "")
        assert prop_text in system_prompt

