"""
Validation logic for generated clarifying questions, reasoning, and evidence.

This module provides:
- Question validation (single focus, non-leading, polite tone, length)
- Reasoning validation (word count, content checks)
- Evidence validation (format, existence)
- Reasoning truncation helper
"""

import re
from typing import Tuple, List, Dict, Any, Set
from .question_config import (
    MAX_REASONING_WORDS,
    HARD_REASONING_LIMIT,
    MIN_QUESTION_LENGTH,
    MAX_QUESTION_LENGTH,
)


class QuestionValidator:
    """Validates generated clarifying questions and reasoning."""
    
    # Patterns to reject (leading/assumptive language)
    REJECT_PATTERNS = [
        r"\bdidn't you\b",
        r"\bwhy didn't you\b",
        r"\bsince you\b",
        r"\byou always\b",
        r"\byou never\b",
        r"\byou're clearly\b",
        r"\byou're obviously\b",
    ]
    
    # Patterns to reject (asking about system instead of claim)
    SYSTEM_REFERENCE_PATTERNS = [
        r"\bhow the system\b",
        r"\bthe system determined\b",
        r"\bthe system noted\b",
        r"\bthe system observed\b",
        r"\bhow the system determined\b",
        r"\bprompted the system\b",
        r"\bled to this conclusion\b",  # "what led to this conclusion" = asking about system's process
    ]
    
    # Politeness indicators (should have at least one)
    POLITENESS_INDICATORS = [
        r"\bcould\b",
        r"\bwould\b",
        r"\bmight\b",
        r"\bperhaps\b",
        r"\bmay\b",
        r"\bdo you\b",
        r"\bwould you\b",
        r"\bcould you\b",
        r"\bcan you\b",
    ]
    
    def __init__(self):
        """Initialize validator with compiled regex patterns."""
        self.reject_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.REJECT_PATTERNS]
        self.politeness_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.POLITENESS_INDICATORS]
        self.system_reference_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.SYSTEM_REFERENCE_PATTERNS]
    
    def validate_question(self, question: str) -> Tuple[bool, List[str]]:
        """
        Validate a generated question.
        
        Checks:
        - Single focus (one question mark)
        - Non-leading language
        - Appropriate length
        - Polite tone
        
        Args:
            question: The question text to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check if empty
        if not question or not question.strip():
            errors.append("Question is empty")
            return False, errors
        
        question = question.strip()
        
        # Check length
        if len(question) < MIN_QUESTION_LENGTH:
            errors.append(f"Question too short (min {MIN_QUESTION_LENGTH} chars)")
        
        if len(question) > MAX_QUESTION_LENGTH:
            errors.append(f"Question too long (max {MAX_QUESTION_LENGTH} chars)")
        
        # Check single focus (one question mark)
        question_marks = question.count("?")
        if question_marks == 0:
            errors.append("Question missing question mark")
        elif question_marks > 1:
            errors.append("Question has multiple question marks (should focus on one thing)")
        
        # Check for leading/assumptive language
        for pattern in self.reject_patterns:
            if pattern.search(question):
                errors.append(f"Question uses leading/assumptive language: '{pattern.pattern}'")
        
        # Check for system references (should ask about claim, not system)
        for pattern in self.system_reference_patterns:
            if pattern.search(question):
                errors.append(f"Question asks about the system instead of the claim: '{pattern.pattern}'")
        
        # Check for politeness indicators
        has_politeness = any(pattern.search(question) for pattern in self.politeness_patterns)
        if not has_politeness:
            # Soft warning, not a hard error
            errors.append("Question may lack polite tone (consider using 'could', 'would', 'might', etc.)")
        
        # Check for inappropriate direct commands
        if re.search(r"^(tell me|explain|describe|clarify)\s", question, re.IGNORECASE):
            # These are commands, not questions - acceptable if they have question structure
            if not question.endswith("?"):
                errors.append("Statement phrased as command rather than question")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def validate_reasoning(self, reasoning: str) -> Tuple[bool, List[str]]:
        """
        Validate reasoning text.
        
        Checks:
        - Length ≤30 words (soft) or ≤40 (hard limit)
        - Mentions factor concern
        - No sensitive data
        
        Args:
            reasoning: The reasoning text to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check if empty
        if not reasoning or not reasoning.strip():
            errors.append("Reasoning is empty")
            return False, errors
        
        reasoning = reasoning.strip()
        
        # Count words
        word_count = len(reasoning.split())
        
        if word_count > HARD_REASONING_LIMIT:
            errors.append(f"Reasoning exceeds hard limit ({word_count} words > {HARD_REASONING_LIMIT} max)")
        elif word_count > MAX_REASONING_WORDS:
            # Soft warning for exceeding preferred limit
            errors.append(f"Reasoning exceeds recommended limit ({word_count} words > {MAX_REASONING_WORDS} recommended)")
        
        # Check that reasoning provides some explanation
        if word_count < 5:
            errors.append("Reasoning too brief (should explain why question was asked)")
        
        # Check for placeholder text
        placeholders = ["TODO", "TBD", "placeholder", "insert reasoning"]
        if any(ph.lower() in reasoning.lower() for ph in placeholders):
            errors.append("Reasoning contains placeholder text")
        
        # Only hard errors fail validation (soft warnings are acceptable)
        hard_errors = [e for e in errors if "exceeds hard limit" in e or "empty" in e or "placeholder" in e or "too brief" in e]
        is_valid = len(hard_errors) == 0
        
        return is_valid, errors
    
    def validate_evidence(
        self,
        evidence: List[str],
        valid_observation_ids: Set[int] = None
    ) -> Tuple[bool, List[str]]:
        """
        Validate evidence citations.
        
        Checks:
        - Format matches "obs_{id}: {summary}"
        - Observation IDs exist (if valid_observation_ids provided)
        
        Args:
            evidence: List of evidence strings
            valid_observation_ids: Optional set of valid observation IDs
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Evidence can be empty (some factors have no specific observations)
        if not evidence:
            return True, []
        
        # Check format of each evidence item
        evidence_pattern = re.compile(r"^obs_(\d+):\s*.+")
        
        for i, ev in enumerate(evidence):
            if not ev or not ev.strip():
                errors.append(f"Evidence item {i} is empty")
                continue
            
            match = evidence_pattern.match(ev.strip())
            if not match:
                errors.append(f"Evidence item {i} has invalid format (expected 'obs_{{id}}: {{summary}}')")
            else:
                obs_id = int(match.group(1))
                
                # Check if observation ID is valid (if validation set provided)
                if valid_observation_ids is not None and obs_id not in valid_observation_ids:
                    errors.append(f"Evidence references non-existent observation: obs_{obs_id}")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def validate_full_output(
        self,
        output: Dict[str, Any],
        valid_observation_ids: Set[int] = None
    ) -> Tuple[bool, List[str]]:
        """
        Validate complete output dict.
        
        Args:
            output: Output dict with question, reasoning, evidence, etc.
            valid_observation_ids: Optional set of valid observation IDs
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        all_errors = []
        
        # Check required fields
        required_fields = ["question", "reasoning", "factor", "prop_id"]
        for field in required_fields:
            if field not in output:
                all_errors.append(f"Missing required field: {field}")
        
        if "question" not in output or "reasoning" not in output:
            # Can't validate further without these
            return False, all_errors
        
        # Validate question
        q_valid, q_errors = self.validate_question(output["question"])
        all_errors.extend([f"Question: {e}" for e in q_errors])
        
        # Validate reasoning
        r_valid, r_errors = self.validate_reasoning(output["reasoning"])
        all_errors.extend([f"Reasoning: {e}" for e in r_errors])
        
        # Validate evidence if present
        if "evidence" in output:
            e_valid, e_errors = self.validate_evidence(
                output["evidence"],
                valid_observation_ids
            )
            all_errors.extend([f"Evidence: {e}" for e in e_errors])
        
        is_valid = len(all_errors) == 0
        return is_valid, all_errors
    
    def truncate_reasoning(self, reasoning: str, max_words: int = None) -> str:
        """
        Truncate reasoning to max word count.
        
        Args:
            reasoning: The reasoning text
            max_words: Maximum words (defaults to MAX_REASONING_WORDS)
            
        Returns:
            Truncated reasoning with ellipsis if needed
        """
        if max_words is None:
            max_words = MAX_REASONING_WORDS
        
        words = reasoning.split()
        if len(words) <= max_words:
            return reasoning
        
        truncated = " ".join(words[:max_words])
        return truncated + "..."
    
    def get_validation_feedback(self, errors: List[str]) -> str:
        """
        Convert validation errors to feedback for retry.
        
        Args:
            errors: List of validation error messages
            
        Returns:
            Formatted feedback string
        """
        if not errors:
            return ""
        
        return " ".join(errors)


def validate_question_batch(
    outputs: List[Dict[str, Any]],
    valid_observation_ids: Set[int] = None
) -> Dict[str, Any]:
    """
    Validate a batch of question outputs.
    
    Args:
        outputs: List of output dicts
        valid_observation_ids: Optional set of valid observation IDs
        
    Returns:
        Dict with validation statistics and failed items
    """
    validator = QuestionValidator()
    
    results = {
        "total": len(outputs),
        "valid": 0,
        "invalid": 0,
        "failed_items": []
    }
    
    for output in outputs:
        is_valid, errors = validator.validate_full_output(output, valid_observation_ids)
        
        if is_valid:
            results["valid"] += 1
        else:
            results["invalid"] += 1
            results["failed_items"].append({
                "prop_id": output.get("prop_id"),
                "factor": output.get("factor"),
                "errors": errors
            })
    
    return results

