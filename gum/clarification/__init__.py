"""
Clarification system for GUM.

This package contains:
- detector.py: Clarification detection (flags propositions)
- question_*: Question generation system (generates clarifying questions)

This __init__.py is minimal to avoid import dependency issues.
"""

# Only import detector-related stuff to avoid circular imports
# Question engine modules can be imported directly
try:
    from .detector import ClarificationDetector
    from .prompts import CLARIFICATION_ANALYSIS_PROMPT
    __all__ = [
        "ClarificationDetector",
        "CLARIFICATION_ANALYSIS_PROMPT",
    ]
except ImportError:
    # If detector dependencies aren't available, just make question modules importable
    __all__ = []
