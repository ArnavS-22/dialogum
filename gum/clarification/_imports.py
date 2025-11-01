"""
Clean import path for clarification question engine modules.

This module allows importing question engine modules without triggering
parent gum package dependencies (sklearn, mss, etc.).

Usage:
    from gum.clarification._imports import QuestionGenerator, QuestionValidator
    # OR
    from gum.clarification import question_config, question_validator
"""

# Re-export question engine modules for easier importing
# These can be imported without triggering gum.__init__.py issues
try:
    from .question_config import (
        get_method_for_factor,
        get_factor_name,
        get_factor_description,
        get_factor_id_from_name,
        FACTOR_METHOD_MAP,
        FACTOR_NAMES,
        FACTOR_DESCRIPTIONS,
    )
    
    from .question_validator import (
        QuestionValidator,
        validate_question_batch,
    )
    
    from .question_prompts import (
        get_few_shot_examples,
        build_few_shot_prompt,
        build_controlled_qg_prompt,
        normalize_proposition_for_prompt,
    )
    
    from .question_loader import (
        load_flagged_propositions,
        filter_propositions,
        get_proposition_factor_pairs,
    )
    
    from .question_generator import (
        QuestionGenerator,
        BatchQuestionGenerator,
    )
    
    from .question_engine import (
        ClarifyingQuestionEngine,
        run_engine_simple,
    )
    
    __all__ = [
        # Config
        "get_method_for_factor",
        "get_factor_name",
        "get_factor_description",
        "get_factor_id_from_name",
        "FACTOR_METHOD_MAP",
        "FACTOR_NAMES",
        "FACTOR_DESCRIPTIONS",
        # Validator
        "QuestionValidator",
        "validate_question_batch",
        # Prompts
        "get_few_shot_examples",
        "build_few_shot_prompt",
        "build_controlled_qg_prompt",
        "normalize_proposition_for_prompt",
        # Loader
        "load_flagged_propositions",
        "filter_propositions",
        "get_proposition_factor_pairs",
        # Generator
        "QuestionGenerator",
        "BatchQuestionGenerator",
        # Engine
        "ClarifyingQuestionEngine",
        "run_engine_simple",
    ]
except ImportError as e:
    # If imports fail, still make module available
    __all__ = []
    import warnings
    warnings.warn(f"Some question engine imports failed: {e}", ImportWarning)

