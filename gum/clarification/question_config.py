"""
Configuration and mappings for clarifying question generation.

This module provides:
- Factor ID to method mapping (few-shot vs controlled QG)
- Factor names and human-readable descriptions
- Validation thresholds and constants
"""

from typing import Optional, Dict

# Factor ID to method mapping
FACTOR_METHOD_MAP: Dict[int, str] = {
    1: "controlled_qg",   # Identity Mismatch
    2: "controlled_qg",   # Surveillance
    3: "few_shot",        # Inferred Intent
    4: "controlled_qg",   # Face Threat
    5: "controlled_qg",   # Over-Positive
    6: "few_shot",        # Opacity
    7: "controlled_qg",   # Generalization
    8: "few_shot",        # Privacy
    9: "controlled_qg",   # Actor-Observer
    10: "controlled_qg",  # Reputation Risk
    11: "few_shot",       # Ambiguity
    12: "controlled_qg"   # Tone Imbalance
}

# Factor names (for prompts/logging)
FACTOR_NAMES: Dict[int, str] = {
    1: "identity_mismatch",
    2: "surveillance",
    3: "inferred_intent",
    4: "face_threat",
    5: "over_positive",
    6: "opacity",
    7: "generalization",
    8: "privacy",
    9: "actor_observer",
    10: "reputation_risk",
    11: "ambiguity",
    12: "tone_imbalance"
}

# Human-readable descriptions (for prompts)
FACTOR_DESCRIPTIONS: Dict[int, str] = {
    1: "Identity Mismatch - The proposition labels you with a personality trait rather than describing behavior",
    2: "Surveillance - The proposition includes overly specific details that feel invasive",
    3: "Inferred Intent - The proposition assumes it knows WHY you did something",
    4: "Face Threat - The proposition is socially critical or disapproving",
    5: "Over-Positive - The proposition gives unexpectedly strong praise",
    6: "Opacity - The proposition makes a confident claim but lacks clear evidence",
    7: "Generalization - The proposition uses absolute language (always, never, all)",
    8: "Privacy - The proposition touches sensitive domains (health, finance, relationships)",
    9: "Actor-Observer Mismatch - The proposition attributes a trait without situational context",
    10: "Reputation Risk - The proposition could affect your social image if shared",
    11: "Ambiguity - The proposition has multiple possible interpretations",
    12: "Tone Imbalance - The proposition's assertiveness doesn't match the evidence"
}

# Validation thresholds
MAX_REASONING_WORDS = 30
HARD_REASONING_LIMIT = 40
MIN_QUESTION_LENGTH = 10
MAX_QUESTION_LENGTH = 200

# Retry settings
MAX_GENERATION_RETRIES = 2

# Evidence settings
MAX_EVIDENCE_ITEMS = 3


def get_method_for_factor(factor_id: int) -> str:
    """
    Get the generation method for a given factor.
    
    Args:
        factor_id: The factor ID (1-12)
        
    Returns:
        Method name: "few_shot" or "controlled_qg"
        
    Raises:
        ValueError: If factor_id is not in valid range
    """
    if factor_id not in FACTOR_METHOD_MAP:
        raise ValueError(f"Invalid factor_id: {factor_id}. Must be 1-12.")
    return FACTOR_METHOD_MAP[factor_id]


def get_factor_name(factor_id: int) -> str:
    """
    Get the name of a factor.
    
    Args:
        factor_id: The factor ID (1-12)
        
    Returns:
        Factor name (e.g., "inferred_intent")
        
    Raises:
        ValueError: If factor_id is not in valid range
    """
    if factor_id not in FACTOR_NAMES:
        raise ValueError(f"Invalid factor_id: {factor_id}. Must be 1-12.")
    return FACTOR_NAMES[factor_id]


def get_factor_description(factor_id: int) -> str:
    """
    Get the human-readable description of a factor.
    
    Args:
        factor_id: The factor ID (1-12)
        
    Returns:
        Factor description
        
    Raises:
        ValueError: If factor_id is not in valid range
    """
    if factor_id not in FACTOR_DESCRIPTIONS:
        raise ValueError(f"Invalid factor_id: {factor_id}. Must be 1-12.")
    return FACTOR_DESCRIPTIONS[factor_id]


def get_factor_id_from_name(factor_name: str) -> Optional[int]:
    """
    Get factor ID from factor name.
    
    Args:
        factor_name: The factor name (e.g., "inferred_intent")
        
    Returns:
        Factor ID (1-12) or None if not found
    """
    for factor_id, name in FACTOR_NAMES.items():
        if name == factor_name:
            return factor_id
    return None


def validate_factor_id(factor_id: int) -> bool:
    """
    Check if a factor ID is valid.
    
    Args:
        factor_id: The factor ID to validate
        
    Returns:
        True if valid, False otherwise
    """
    return factor_id in FACTOR_METHOD_MAP


def get_all_factor_ids() -> list[int]:
    """
    Get all valid factor IDs.
    
    Returns:
        List of all factor IDs (1-12)
    """
    return list(FACTOR_METHOD_MAP.keys())


def get_few_shot_factor_ids() -> list[int]:
    """
    Get factor IDs that use few-shot generation.
    
    Returns:
        List of factor IDs that use few-shot method
    """
    return [fid for fid, method in FACTOR_METHOD_MAP.items() if method == "few_shot"]


def get_controlled_qg_factor_ids() -> list[int]:
    """
    Get factor IDs that use controlled QG generation.
    
    Returns:
        List of factor IDs that use controlled QG method
    """
    return [fid for fid, method in FACTOR_METHOD_MAP.items() if method == "controlled_qg"]

