# urgency_detector.py
"""
Determines urgency of clarification based on ambiguity, confidence, and temporal factors.
Assigns URGENT, SOON, or LATER tags to prioritize when to initiate GATE dialogues.
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from ..ambiguity_config import UrgencyConfig, DEFAULT_CONFIG
from .entropy_calculator import EntropyResult


@dataclass
class UrgencyResult:
    """Result of urgency assessment.
    
    Attributes:
        urgency_level: URGENT, SOON, or LATER.
        urgency_score: Continuous score (0-1) used for ranking.
        reasoning: Human-readable explanation.
        time_sensitive: Whether proposition contains time-sensitive language.
        confidence_factor: How much confidence contributed (0-1).
        ambiguity_factor: How much entropy contributed (0-1).
        temporal_factor: How much temporal keywords contributed (0-1).
        temporal_keywords: List of detected time-related keywords.
        should_clarify_by: Recommended deadline for clarification.
    """
    urgency_level: str
    urgency_score: float
    reasoning: str
    time_sensitive: bool
    confidence_factor: float
    ambiguity_factor: float
    temporal_factor: float
    temporal_keywords: List[str]
    should_clarify_by: Optional[datetime]


class UrgencyDetector:
    """Detects urgency of clarification for ambiguous propositions."""
    
    def __init__(self, config: UrgencyConfig = None):
        """Initialize detector.
        
        Args:
            config: Urgency configuration with thresholds and weights.
        """
        self.config = config or DEFAULT_CONFIG.urgency
    
    def _detect_temporal_keywords(self, text: str) -> List[str]:
        """Detect time-sensitive keywords in text.
        
        Args:
            text: Proposition text to analyze.
            
        Returns:
            List of detected temporal keywords.
        """
        text_lower = text.lower()
        found_keywords = []
        
        for keyword in self.config.temporal_keywords:
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, text_lower):
                found_keywords.append(keyword)
        
        return found_keywords
    
    def _compute_confidence_factor(self, confidence: Optional[int]) -> float:
        """Compute confidence contribution to urgency (0-1).
        
        Lower confidence → higher urgency.
        
        Args:
            confidence: GUM's confidence score (1-10), or None.
            
        Returns:
            Confidence factor (0-1). Higher means more urgent.
        """
        if confidence is None:
            # No confidence info → assume moderate urgency
            return 0.5
        
        # Invert and normalize: 1/10 = 0.9, 10/10 = 0.0
        # Low confidence = high urgency
        normalized = (10 - confidence) / 10.0
        
        # Apply thresholds for more nuanced scoring
        if confidence <= self.config.low_confidence_threshold:
            # Very low confidence → high urgency factor
            return 0.8 + (normalized * 0.2)  # 0.8-1.0
        elif confidence >= self.config.high_confidence_threshold:
            # High confidence → low urgency factor
            return normalized * 0.3  # 0.0-0.3
        else:
            # Medium confidence → moderate urgency
            return 0.3 + (normalized * 0.5)  # 0.3-0.8
    
    def _compute_ambiguity_factor(self, entropy_result: EntropyResult) -> float:
        """Compute ambiguity contribution to urgency (0-1).
        
        Higher entropy → higher urgency.
        
        Args:
            entropy_result: Result from entropy calculator.
            
        Returns:
            Ambiguity factor (0-1). Higher means more urgent.
        """
        # Use normalized entropy (0-1 range)
        normalized_entropy = entropy_result.normalized_entropy
        
        # Apply sigmoid-like transformation for smoother scaling
        # Very low entropy → low urgency
        # Very high entropy → high urgency
        if normalized_entropy < 0.3:
            return normalized_entropy * 0.5  # 0.0-0.15
        elif normalized_entropy > 0.7:
            return 0.6 + (normalized_entropy - 0.7) * 1.33  # 0.6-1.0
        else:
            return 0.15 + (normalized_entropy - 0.3) * 1.125  # 0.15-0.6
    
    def _compute_temporal_factor(
        self,
        temporal_keywords: List[str],
        proposition_text: str
    ) -> float:
        """Compute temporal sensitivity contribution to urgency (0-1).
        
        Args:
            temporal_keywords: Detected temporal keywords.
            proposition_text: Full proposition text for context.
            
        Returns:
            Temporal factor (0-1). Higher means more urgent.
        """
        if not temporal_keywords:
            return 0.0
        
        # Base score from number of keywords (with diminishing returns)
        keyword_count = len(temporal_keywords)
        base_score = min(keyword_count * 0.2, 0.6)
        
        # Boost for high-urgency keywords
        high_urgency_words = {"now", "today", "urgent", "deadline", "immediately"}
        has_high_urgency = any(kw in high_urgency_words for kw in temporal_keywords)
        
        if has_high_urgency:
            boost = 0.3
        else:
            boost = 0.1
        
        return min(base_score + boost, 1.0)
    
    def _compute_urgency_score(
        self,
        confidence_factor: float,
        ambiguity_factor: float,
        temporal_factor: float
    ) -> float:
        """Compute overall urgency score as weighted sum.
        
        Args:
            confidence_factor: Confidence contribution (0-1).
            ambiguity_factor: Ambiguity contribution (0-1).
            temporal_factor: Temporal contribution (0-1).
            
        Returns:
            Urgency score (0-1).
        """
        score = (
            self.config.confidence_weight * confidence_factor +
            self.config.ambiguity_weight * ambiguity_factor +
            self.config.temporal_weight * temporal_factor
        )
        
        # Clamp to [0, 1]
        return max(0.0, min(1.0, score))
    
    def _assign_urgency_level(self, urgency_score: float) -> str:
        """Assign categorical urgency level based on score.
        
        Args:
            urgency_score: Continuous urgency score (0-1).
            
        Returns:
            "URGENT", "SOON", or "LATER".
        """
        if urgency_score >= self.config.urgent_threshold:
            return "URGENT"
        elif urgency_score >= self.config.soon_threshold:
            return "SOON"
        else:
            return "LATER"
    
    def _compute_clarification_deadline(self, urgency_level: str) -> datetime:
        """Compute recommended deadline for clarification.
        
        Args:
            urgency_level: URGENT, SOON, or LATER.
            
        Returns:
            Datetime when clarification should be completed by.
        """
        now = datetime.now()
        
        if urgency_level == "URGENT":
            return now + timedelta(hours=self.config.urgent_clarify_hours)
        elif urgency_level == "SOON":
            return now + timedelta(hours=self.config.soon_clarify_hours)
        else:  # LATER
            return now + timedelta(hours=self.config.later_clarify_hours)
    
    def _generate_reasoning(
        self,
        urgency_level: str,
        urgency_score: float,
        confidence: Optional[int],
        entropy_result: EntropyResult,
        temporal_keywords: List[str]
    ) -> str:
        """Generate human-readable reasoning for urgency assignment.
        
        Args:
            urgency_level: Assigned urgency level.
            urgency_score: Computed urgency score.
            confidence: GUM's confidence.
            entropy_result: Entropy analysis result.
            temporal_keywords: Detected temporal keywords.
            
        Returns:
            Reasoning string.
        """
        reasons = []
        
        # Ambiguity reason
        if entropy_result.entropy_score > 1.5:
            reasons.append(f"high ambiguity (entropy: {entropy_result.entropy_score:.2f} bits)")
        elif entropy_result.entropy_score > 0.8:
            reasons.append(f"moderate ambiguity (entropy: {entropy_result.entropy_score:.2f} bits)")
        
        # Confidence reason
        if confidence is not None:
            if confidence <= self.config.low_confidence_threshold:
                reasons.append(f"low confidence ({confidence}/10)")
            elif confidence >= self.config.high_confidence_threshold:
                reasons.append(f"high confidence ({confidence}/10)")
        
        # Temporal reason
        if temporal_keywords:
            reasons.append(f"time-sensitive language ({', '.join(temporal_keywords[:3])})")
        
        if not reasons:
            reasons.append("standard assessment based on thresholds")
        
        reasoning = f"{urgency_level}: " + " + ".join(reasons)
        reasoning += f" (score: {urgency_score:.2f})"
        
        return reasoning
    
    def assess(
        self,
        entropy_result: EntropyResult,
        proposition_text: str,
        confidence: Optional[int] = None
    ) -> UrgencyResult:
        """Assess urgency of clarification for a proposition.
        
        Args:
            entropy_result: Result from entropy calculation.
            proposition_text: The proposition text to analyze.
            confidence: GUM's confidence score (1-10), optional.
            
        Returns:
            UrgencyResult with level, score, and reasoning.
        """
        # Detect temporal keywords
        temporal_keywords = self._detect_temporal_keywords(proposition_text)
        time_sensitive = len(temporal_keywords) > 0
        
        # Compute individual factors
        confidence_factor = self._compute_confidence_factor(confidence)
        ambiguity_factor = self._compute_ambiguity_factor(entropy_result)
        temporal_factor = self._compute_temporal_factor(temporal_keywords, proposition_text)
        
        # Compute overall urgency score
        urgency_score = self._compute_urgency_score(
            confidence_factor,
            ambiguity_factor,
            temporal_factor
        )
        
        # Assign categorical level
        urgency_level = self._assign_urgency_level(urgency_score)
        
        # Compute deadline
        deadline = self._compute_clarification_deadline(urgency_level)
        
        # Generate reasoning
        reasoning = self._generate_reasoning(
            urgency_level,
            urgency_score,
            confidence,
            entropy_result,
            temporal_keywords
        )
        
        return UrgencyResult(
            urgency_level=urgency_level,
            urgency_score=urgency_score,
            reasoning=reasoning,
            time_sensitive=time_sensitive,
            confidence_factor=confidence_factor,
            ambiguity_factor=ambiguity_factor,
            temporal_factor=temporal_factor,
            temporal_keywords=temporal_keywords,
            should_clarify_by=deadline
        )


def format_urgency_for_storage(result: UrgencyResult) -> Dict:
    """Convert urgency result to JSON-serializable dict.
    
    Args:
        result: UrgencyResult object.
        
    Returns:
        Dict for database storage.
    """
    return {
        "urgency_level": result.urgency_level,
        "urgency_score": float(result.urgency_score),
        "reasoning": result.reasoning,
        "time_sensitive": result.time_sensitive,
        "confidence_factor": float(result.confidence_factor),
        "ambiguity_factor": float(result.ambiguity_factor),
        "temporal_factor": float(result.temporal_factor),
        "temporal_keywords": result.temporal_keywords,
        "should_clarify_by": result.should_clarify_by.isoformat() if result.should_clarify_by else None
    }
