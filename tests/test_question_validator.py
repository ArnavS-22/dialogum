"""
Unit tests for question_validator module.

Tests:
- Question validation (single focus, non-leading, polite tone, length)
- Reasoning validation (word count, content)
- Evidence validation (format, IDs)
- Full output validation
- Truncation helper
"""

import pytest
from gum.clarification.question_validator import (
    QuestionValidator,
    validate_question_batch
)


class TestQuestionValidation:
    """Test question validation logic."""
    
    def setup_method(self):
        """Setup validator instance."""
        self.validator = QuestionValidator()
    
    def test_valid_question(self):
        """Test validation of a good question."""
        question = "Could you clarify what you mean by 'structured thinking'?"
        is_valid, errors = self.validator.validate_question(question)
        assert is_valid
        assert len(errors) == 0
    
    def test_question_too_short(self):
        """Test rejection of too-short questions."""
        question = "Why?"
        is_valid, errors = self.validator.validate_question(question)
        assert not is_valid
        assert any("too short" in e for e in errors)
    
    def test_question_missing_question_mark(self):
        """Test rejection of questions without question mark."""
        question = "Could you clarify what you mean by structured thinking"
        is_valid, errors = self.validator.validate_question(question)
        assert not is_valid
        assert any("missing question mark" in e for e in errors)
    
    def test_question_multiple_question_marks(self):
        """Test rejection of multiple questions."""
        question = "Could you clarify this? And also that?"
        is_valid, errors = self.validator.validate_question(question)
        assert not is_valid
        assert any("multiple question marks" in e for e in errors)
    
    def test_question_leading_language(self):
        """Test rejection of leading/assumptive language."""
        # Test various leading patterns
        leading_questions = [
            "Didn't you say that you liked it?",
            "Since you always do that, why did you do it again?",
            "You always interrupt meetings, don't you?",
            "You're clearly a perfectionist, aren't you?"
        ]
        
        for question in leading_questions:
            is_valid, errors = self.validator.validate_question(question)
            assert not is_valid
            assert any("leading" in e or "assumptive" in e for e in errors)
    
    def test_question_politeness_indicators(self):
        """Test that polite questions pass."""
        polite_questions = [
            "Could you explain what you meant?",
            "Would you prefer a different phrasing?",
            "Might this be related to the earlier observation?",
            "Do you think this applies to your situation?"
        ]
        
        for question in polite_questions:
            is_valid, errors = self.validator.validate_question(question)
            # Should pass or have only soft warnings
            assert is_valid or all("may lack polite tone" in e for e in errors)
    
    def test_empty_question(self):
        """Test rejection of empty questions."""
        is_valid, errors = self.validator.validate_question("")
        assert not is_valid
        assert any("empty" in e for e in errors)


class TestReasoningValidation:
    """Test reasoning validation logic."""
    
    def setup_method(self):
        """Setup validator instance."""
        self.validator = QuestionValidator()
    
    def test_valid_reasoning(self):
        """Test validation of good reasoning."""
        reasoning = "This proposition infers motive from messaging patterns; clarifying confirms the actual intent."
        is_valid, errors = self.validator.validate_reasoning(reasoning)
        assert is_valid
        assert len(errors) == 0
    
    def test_reasoning_slightly_over_soft_limit(self):
        """Test reasoning over soft limit but under hard limit."""
        # 35 words (over 30 soft limit, under 40 hard limit)
        reasoning = " ".join(["word"] * 35)
        is_valid, errors = self.validator.validate_reasoning(reasoning)
        # Should pass with warning
        assert is_valid
        assert any("recommended limit" in e for e in errors)
    
    def test_reasoning_over_hard_limit(self):
        """Test reasoning over hard limit."""
        # 45 words (over 40 hard limit)
        reasoning = " ".join(["word"] * 45)
        is_valid, errors = self.validator.validate_reasoning(reasoning)
        assert not is_valid
        assert any("hard limit" in e for e in errors)
    
    def test_reasoning_too_brief(self):
        """Test reasoning that's too short."""
        reasoning = "Too short"
        is_valid, errors = self.validator.validate_reasoning(reasoning)
        assert not is_valid
        assert any("too brief" in e for e in errors)
    
    def test_reasoning_with_placeholder(self):
        """Test rejection of placeholder text."""
        placeholders = [
            "TODO: write reasoning",
            "TBD placeholder text",
            "Insert reasoning here"
        ]
        
        for reasoning in placeholders:
            is_valid, errors = self.validator.validate_reasoning(reasoning)
            assert not is_valid
            assert any("placeholder" in e for e in errors)
    
    def test_empty_reasoning(self):
        """Test rejection of empty reasoning."""
        is_valid, errors = self.validator.validate_reasoning("")
        assert not is_valid
        assert any("empty" in e for e in errors)


class TestEvidenceValidation:
    """Test evidence validation logic."""
    
    def setup_method(self):
        """Setup validator instance."""
        self.validator = QuestionValidator()
    
    def test_valid_evidence(self):
        """Test validation of properly formatted evidence."""
        evidence = [
            "obs_451: multiple WhatsApp Web sessions on 2025-09-29",
            "obs_452: opened chat with 3 different contacts"
        ]
        is_valid, errors = self.validator.validate_evidence(evidence)
        assert is_valid
        assert len(errors) == 0
    
    def test_empty_evidence(self):
        """Test that empty evidence is acceptable."""
        is_valid, errors = self.validator.validate_evidence([])
        assert is_valid
        assert len(errors) == 0
    
    def test_invalid_evidence_format(self):
        """Test rejection of incorrectly formatted evidence."""
        invalid_evidence = [
            "observation 451: some text",  # Wrong format
            "obs_452",  # Missing colon and text
            "just some text"  # No obs_ prefix
        ]
        
        for evidence in invalid_evidence:
            is_valid, errors = self.validator.validate_evidence([evidence])
            assert not is_valid
            assert any("invalid format" in e for e in errors)
    
    def test_evidence_with_valid_obs_ids(self):
        """Test evidence validation with ID checking."""
        evidence = [
            "obs_451: some observation",
            "obs_452: another observation"
        ]
        valid_ids = {451, 452}
        
        is_valid, errors = self.validator.validate_evidence(evidence, valid_ids)
        assert is_valid
        assert len(errors) == 0
    
    def test_evidence_with_invalid_obs_ids(self):
        """Test rejection of non-existent observation IDs."""
        evidence = [
            "obs_451: some observation",
            "obs_999: non-existent observation"
        ]
        valid_ids = {451, 452}
        
        is_valid, errors = self.validator.validate_evidence(evidence, valid_ids)
        assert not is_valid
        assert any("non-existent observation" in e for e in errors)


class TestFullOutputValidation:
    """Test full output validation."""
    
    def setup_method(self):
        """Setup validator instance."""
        self.validator = QuestionValidator()
    
    def test_valid_full_output(self):
        """Test validation of complete valid output."""
        output = {
            "prop_id": 77,
            "factor": "inferred_intent",
            "question": "Could you clarify what you meant by that?",
            "reasoning": "This proposition infers motive; clarifying confirms intent.",
            "evidence": ["obs_451: some observation"]
        }
        
        is_valid, errors = self.validator.validate_full_output(output)
        assert is_valid
        assert len(errors) == 0
    
    def test_output_missing_required_fields(self):
        """Test rejection of output missing required fields."""
        output = {
            "prop_id": 77,
            "question": "What do you think?"
            # Missing reasoning and factor
        }
        
        is_valid, errors = self.validator.validate_full_output(output)
        assert not is_valid
        assert any("Missing required field" in e for e in errors)
    
    def test_output_with_invalid_question_and_reasoning(self):
        """Test output with multiple validation errors."""
        output = {
            "prop_id": 77,
            "factor": "inferred_intent",
            "question": "Why",  # Too short, no question mark
            "reasoning": "TODO",  # Placeholder
            "evidence": []
        }
        
        is_valid, errors = self.validator.validate_full_output(output)
        assert not is_valid
        # Should have errors for both question and reasoning
        assert any("Question:" in e for e in errors)
        assert any("Reasoning:" in e for e in errors)


class TestReasoningTruncation:
    """Test reasoning truncation helper."""
    
    def setup_method(self):
        """Setup validator instance."""
        self.validator = QuestionValidator()
    
    def test_truncate_reasoning_under_limit(self):
        """Test that reasoning under limit is not truncated."""
        reasoning = "This is a short reasoning text."
        truncated = self.validator.truncate_reasoning(reasoning, max_words=30)
        assert truncated == reasoning
    
    def test_truncate_reasoning_over_limit(self):
        """Test that reasoning over limit is truncated."""
        words = ["word"] * 50
        reasoning = " ".join(words)
        
        truncated = self.validator.truncate_reasoning(reasoning, max_words=30)
        truncated_words = truncated.replace("...", "").split()
        
        assert len(truncated_words) == 30
        assert truncated.endswith("...")
    
    def test_truncate_reasoning_default_limit(self):
        """Test truncation with default max_words."""
        words = ["word"] * 50
        reasoning = " ".join(words)
        
        truncated = self.validator.truncate_reasoning(reasoning)
        # Should use MAX_REASONING_WORDS default (30)
        truncated_words = truncated.replace("...", "").split()
        assert len(truncated_words) == 30


class TestValidationFeedback:
    """Test validation feedback generation."""
    
    def setup_method(self):
        """Setup validator instance."""
        self.validator = QuestionValidator()
    
    def test_get_validation_feedback(self):
        """Test conversion of errors to feedback string."""
        errors = [
            "Question too short",
            "Missing question mark",
            "Reasoning too long"
        ]
        
        feedback = self.validator.get_validation_feedback(errors)
        assert isinstance(feedback, str)
        assert "Question too short" in feedback
        assert "Missing question mark" in feedback
        assert "Reasoning too long" in feedback
    
    def test_get_validation_feedback_empty(self):
        """Test feedback for no errors."""
        feedback = self.validator.get_validation_feedback([])
        assert feedback == ""


class TestBatchValidation:
    """Test batch validation helper."""
    
    def test_validate_question_batch(self):
        """Test batch validation of multiple outputs."""
        outputs = [
            {
                "prop_id": 1,
                "factor": "inferred_intent",
                "question": "Could you clarify what you meant?",
                "reasoning": "This checks the intent.",
                "evidence": []
            },
            {
                "prop_id": 2,
                "factor": "opacity",
                "question": "Why",  # Invalid
                "reasoning": "Too brief",
                "evidence": []
            },
            {
                "prop_id": 3,
                "factor": "ambiguity",
                "question": "What does 'development' mean here?",
                "reasoning": "The term is ambiguous.",
                "evidence": []
            }
        ]
        
        results = validate_question_batch(outputs)
        
        assert results["total"] == 3
        assert results["valid"] == 2
        assert results["invalid"] == 1
        assert len(results["failed_items"]) == 1
        assert results["failed_items"][0]["prop_id"] == 2


class TestPropertyBasedValidation:
    """Property-based tests for validation invariants."""
    
    def setup_method(self):
        """Setup validator instance."""
        self.validator = QuestionValidator()
    
    def test_validation_is_deterministic(self):
        """Test that validation produces same result for same input."""
        question = "Could you clarify what you mean by 'structured thinking'?"
        
        result1 = self.validator.validate_question(question)
        result2 = self.validator.validate_question(question)
        
        assert result1 == result2
    
    def test_empty_strings_always_invalid(self):
        """Test that empty strings always fail validation."""
        assert not self.validator.validate_question("")[0]
        assert not self.validator.validate_reasoning("")[0]
    
    def test_truncation_idempotent(self):
        """Test that truncating already-short text doesn't change it."""
        short_text = "Short text"
        truncated = self.validator.truncate_reasoning(short_text, max_words=30)
        assert truncated == short_text
        
        # Truncate again
        truncated2 = self.validator.truncate_reasoning(truncated, max_words=30)
        assert truncated2 == truncated

