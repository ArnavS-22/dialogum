# entropy_calculator.py
"""
Computes Shannon entropy over cluster distributions to quantify ambiguity.
Core metric for detecting whether propositions need clarification.
"""

import numpy as np
from typing import Dict, Tuple
from dataclasses import dataclass

from ..ambiguity_config import EntropyConfig, DEFAULT_CONFIG
from .clustering import ClusterResult, get_cluster_distribution


@dataclass
class EntropyResult:
    """Result of entropy calculation.
    
    Attributes:
        entropy_score: Shannon entropy in bits (0 = unambiguous, higher = more ambiguous).
        normalized_entropy: Entropy divided by log2(num_clusters), range [0, 1].
        is_ambiguous: Binary classification based on threshold.
        threshold_used: The threshold applied.
        num_clusters: Number of clusters in distribution.
        distribution: Probability distribution over clusters.
    """
    entropy_score: float
    normalized_entropy: float
    is_ambiguous: bool
    threshold_used: float
    num_clusters: int
    distribution: np.ndarray


class EntropyCalculator:
    """Calculates Shannon entropy to quantify ambiguity."""
    
    def __init__(self, config: EntropyConfig = None):
        """Initialize calculator.
        
        Args:
            config: Entropy configuration with thresholds.
        """
        self.config = config or DEFAULT_CONFIG.entropy
    
    def _compute_shannon_entropy(self, distribution: np.ndarray) -> float:
        """Compute Shannon entropy: H = -Σ(p_i * log2(p_i))
        
        Args:
            distribution: Probability distribution (sums to 1).
            
        Returns:
            Entropy in bits.
        """
        # Filter out zero probabilities (log(0) is undefined)
        non_zero = distribution[distribution > 0]
        
        if len(non_zero) == 0:
            return 0.0
        
        # Shannon entropy formula
        entropy = -np.sum(non_zero * np.log2(non_zero))
        
        return float(entropy)
    
    def calculate(
        self,
        cluster_result: ClusterResult,
        use_normalized: bool = None
    ) -> EntropyResult:
        """Calculate entropy from clustering result.
        
        Args:
            cluster_result: Result from semantic clustering.
            use_normalized: Whether to use normalized entropy (override config).
            
        Returns:
            EntropyResult with score and classification.
        """
        # Get probability distribution
        distribution = get_cluster_distribution(cluster_result)
        
        if len(distribution) == 0:
            # No valid clusters
            return EntropyResult(
                entropy_score=0.0,
                normalized_entropy=0.0,
                is_ambiguous=False,
                threshold_used=self.config.ambiguity_threshold,
                num_clusters=0,
                distribution=distribution
            )
        
        # Compute raw entropy
        entropy = self._compute_shannon_entropy(distribution)
        
        # Normalize if configured
        use_norm = use_normalized if use_normalized is not None else self.config.use_normalized_entropy
        
        if use_norm and cluster_result.num_clusters > 1:
            # Max entropy = log2(num_clusters) (uniform distribution)
            max_entropy = np.log2(cluster_result.num_clusters)
            normalized = entropy / max_entropy if max_entropy > 0 else 0.0
        else:
            normalized = entropy
        
        # Apply threshold to raw (un-normalized) entropy
        # Threshold is calibrated for raw entropy values
        is_ambiguous = entropy >= self.config.ambiguity_threshold
        
        return EntropyResult(
            entropy_score=entropy,
            normalized_entropy=normalized,
            is_ambiguous=is_ambiguous,
            threshold_used=self.config.ambiguity_threshold,
            num_clusters=cluster_result.num_clusters,
            distribution=distribution
        )
    
    def calculate_from_distribution(
        self,
        distribution: np.ndarray,
        threshold: float = None
    ) -> EntropyResult:
        """Calculate entropy directly from a probability distribution.
        
        Useful for testing or when you already have the distribution.
        
        Args:
            distribution: Probability distribution (should sum to 1).
            threshold: Override default threshold.
            
        Returns:
            EntropyResult.
        """
        if not np.isclose(distribution.sum(), 1.0, atol=0.01):
            raise ValueError(f"Distribution must sum to 1.0, got {distribution.sum()}")
        
        entropy = self._compute_shannon_entropy(distribution)
        num_clusters = len(distribution)
        
        if num_clusters > 1:
            max_entropy = np.log2(num_clusters)
            normalized = entropy / max_entropy
        else:
            normalized = entropy
        
        threshold = threshold or self.config.ambiguity_threshold
        is_ambiguous = entropy >= threshold
        
        return EntropyResult(
            entropy_score=entropy,
            normalized_entropy=normalized,
            is_ambiguous=is_ambiguous,
            threshold_used=threshold,
            num_clusters=num_clusters,
            distribution=distribution
        )


def format_entropy_for_storage(result: EntropyResult) -> Dict:
    """Convert entropy result to JSON-serializable dict.
    
    Args:
        result: EntropyResult object.
        
    Returns:
        Dict for database storage.
    """
    return {
        "entropy_score": float(result.entropy_score),
        "normalized_entropy": float(result.normalized_entropy),
        "is_ambiguous": bool(result.is_ambiguous),
        "threshold_used": float(result.threshold_used),
        "num_clusters": int(result.num_clusters),
        "distribution": result.distribution.tolist()
    }


def interpret_entropy(entropy_score: float) -> str:
    """Human-readable interpretation of entropy score.
    
    Args:
        entropy_score: Raw entropy in bits.
        
    Returns:
        Interpretation string.
    """
    if entropy_score < 0.3:
        return "Very Low - Proposition is unambiguous"
    elif entropy_score < 0.8:
        return "Low - Minor ambiguity, likely clear"
    elif entropy_score < 1.2:
        return "Moderate - Ambiguous, clarification recommended"
    elif entropy_score < 1.8:
        return "High - Significantly ambiguous, clarification needed"
    else:
        return "Very High - Highly ambiguous, urgent clarification needed"
