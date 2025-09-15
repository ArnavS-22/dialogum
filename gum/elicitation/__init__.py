"""
Generative Elicitation Module

This module provides active learning agents for eliciting human preferences
through generative AI. It includes various strategies for querying users
to understand their preferences and requirements.

Key Components:
- BaseActiveLearningAgent: Abstract base class for active learning agents
- GenerativeQuestionsAgent: Generates questions to elicit preferences
- GenerativeEdgeCasesAgent: Generates edge cases to understand boundaries
- PoolBasedAgent: Uses pool-based active learning strategies
- FromSavedFileAgent: Loads and uses pre-saved interaction data

This module is based on the work from:
https://github.com/alextamkin/generative-elicitation
"""

from .base_active_learning_agent import BaseActiveLearningAgent
from .generative_questions_agent import GenerativeQuestionsAgent
from .generative_edge_cases_agent import GenerativeEdgeCasesAgent
from .pool_based_agent import PoolBasedAgent
from .from_saved_file_agent import FromSavedFileAgent
from .utils import query_api, load_openai_cache, save_openai_cache

__all__ = [
    'BaseActiveLearningAgent',
    'GenerativeQuestionsAgent', 
    'GenerativeEdgeCasesAgent',
    'PoolBasedAgent',
    'FromSavedFileAgent',
    'query_api',
    'load_openai_cache',
    'save_openai_cache'
]
