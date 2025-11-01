"""
Clarification system for GUM.

This package contains:
- detector.py: Clarification detection (flags propositions)
- question_*: Question generation system (generates clarifying questions)
"""

# Only import detector-related stuff to avoid circular imports
# Question engine modules can be imported directly
from .detector import ClarificationDetector
from .prompts import CLARIFICATION_ANALYSIS_PROMPT

__all__ = [
    "ClarificationDetector",
    "CLARIFICATION_ANALYSIS_PROMPT",
]
