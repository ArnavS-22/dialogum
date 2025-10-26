"""
Clarification Detection Engine for GUM.

This module implements a comprehensive system for detecting when propositions
should be flagged for clarifying dialogue based on 12 psychological factors.
"""

from .detector import ClarificationDetector
from .prompts import CLARIFICATION_ANALYSIS_PROMPT

__all__ = ["ClarificationDetector", "CLARIFICATION_ANALYSIS_PROMPT"]

