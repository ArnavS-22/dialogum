# ambiguity_config.py
"""
Configuration for ambiguity detection and urgency assessment pipeline.
Contains thresholds, model parameters, and heuristics.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class InterpretationConfig:
    """Configuration for interpretation generation."""
    model: str = "gpt-4"
    temperature: float = 1.0  # High for diversity
    max_tokens: int = 500
    min_interpretations: int = 2
    max_interpretations: int = 4
    timeout_seconds: int = 30


@dataclass
class AnswerCollectionConfig:
    """Configuration for answer collection per interpretation."""
    model: str = "gpt-3.5-turbo"  # Cheaper model for sampling
    num_answers_per_interpretation: int = 8
    temperature: float = 0.8  # Moderate randomness
    max_tokens: int = 150
    timeout_seconds: int = 20


@dataclass
class ClusteringConfig:
    """Configuration for semantic clustering."""
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    clustering_method: str = "hdbscan"  # or "kmeans"
    min_cluster_size: int = 2
    min_samples: int = 1
    similarity_threshold: float = 0.75  # For pairwise clustering fallback


@dataclass
class EntropyConfig:
    """Configuration for entropy computation and ambiguity detection."""
    # Entropy threshold for binary classification
    # Values based on UCSB paper + calibration
    # Typical range: 0.5-1.5 bits (log2 scale)
    ambiguity_threshold: float = 0.8
    
    # Confidence intervals for entropy
    low_entropy: float = 0.3  # Clearly unambiguous
    high_entropy: float = 1.5  # Clearly ambiguous
    
    # Normalization
    use_normalized_entropy: bool = True  # Divide by log2(num_clusters)


@dataclass
class UrgencyConfig:
    """Configuration for urgency assessment heuristics."""
    
    # Urgency score weights (sum to 1.0)
    ambiguity_weight: float = 0.4
    confidence_weight: float = 0.3
    temporal_weight: float = 0.3
    
    # Thresholds for urgency levels (on 0-1 score)
    urgent_threshold: float = 0.7  # >= 0.7 -> URGENT
    soon_threshold: float = 0.4    # >= 0.4 -> SOON, else LATER
    
    # Temporal keywords that trigger time-sensitivity
    temporal_keywords: List[str] = field(default_factory=lambda: [
        "today", "tomorrow", "now", "currently", "soon", "urgent",
        "deadline", "schedule", "meeting", "appointment", "event",
        "recently", "just", "about to", "planning to", "will"
    ])
    
    # Confidence thresholds (GUM's 1-10 scale)
    low_confidence_threshold: int = 4
    high_confidence_threshold: int = 8
    
    # Time window for clarification recommendations
    urgent_clarify_hours: int = 2
    soon_clarify_hours: int = 24
    later_clarify_hours: int = 168  # 1 week


@dataclass
class PipelineConfig:
    """Master configuration for the full ambiguity pipeline."""
    
    interpretation: InterpretationConfig = field(default_factory=InterpretationConfig)
    answer_collection: AnswerCollectionConfig = field(default_factory=AnswerCollectionConfig)
    clustering: ClusteringConfig = field(default_factory=ClusteringConfig)
    entropy: EntropyConfig = field(default_factory=EntropyConfig)
    urgency: UrgencyConfig = field(default_factory=UrgencyConfig)
    
    # Pipeline behavior
    enable_caching: bool = True
    cache_ttl_hours: int = 24
    batch_size: int = 10
    max_concurrent: int = 5
    
    # Error handling
    max_retries: int = 3
    retry_delay_seconds: float = 2.0
    
    def to_dict(self):
        """Convert config to dictionary for storage."""
        return {
            "interpretation": {
                "model": self.interpretation.model,
                "temperature": self.interpretation.temperature,
                "max_tokens": self.interpretation.max_tokens,
            },
            "answer_collection": {
                "model": self.answer_collection.model,
                "num_answers": self.answer_collection.num_answers_per_interpretation,
                "temperature": self.answer_collection.temperature,
            },
            "clustering": {
                "method": self.clustering.clustering_method,
                "embedding_model": self.clustering.embedding_model,
            },
            "entropy": {
                "threshold": self.entropy.ambiguity_threshold,
                "use_normalized": self.entropy.use_normalized_entropy,
            },
            "urgency": {
                "weights": {
                    "ambiguity": self.urgency.ambiguity_weight,
                    "confidence": self.urgency.confidence_weight,
                    "temporal": self.urgency.temporal_weight,
                },
                "thresholds": {
                    "urgent": self.urgency.urgent_threshold,
                    "soon": self.urgency.soon_threshold,
                }
            }
        }


# Default configuration instance
DEFAULT_CONFIG = PipelineConfig()


def load_config(config_path: str = None) -> PipelineConfig:
    """Load configuration from file or return default.
    
    Args:
        config_path: Path to JSON/YAML config file (optional).
        
    Returns:
        PipelineConfig instance.
    """
    if config_path is None:
        return DEFAULT_CONFIG
    
    # TODO: Implement file loading when needed
    import json
    with open(config_path, 'r') as f:
        config_dict = json.load(f)
    
    # Update defaults with loaded values
    config = PipelineConfig()
    # ... merge logic here
    return config
