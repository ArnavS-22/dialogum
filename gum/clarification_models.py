# clarification_models.py
"""
Database models for the Clarification Detection Engine.

This module defines the schema for storing clarification analysis results
for GUM propositions. Each proposition can be analyzed against 12 psychological
factors to determine if it should be flagged for clarifying dialogue.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Float, String, Text, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .models import Base, Proposition


class ClarificationAnalysis(Base):
    """Stores clarification detection results for propositions.
    
    Analyzes each proposition against 12 research-grounded psychological factors
    that predict when humans want to clarify or question a statement about them.
    
    The 12 factors are:
    1. Identity Mismatch / Self-Verification Conflict
    2. Over-Specific Behavioral Claim (Surveillance)
    3. Inferred Motives / Intent Attribution
    4. Negative Evaluation / Face Threat
    5. Over-Positive / Surprising Claim
    6. Lack of Evidence / Opaque Reasoning
    7. Over-Generalization / Absolutist Language
    8. Sensitive / Intimate Domain
    9. Actor-Observer Mismatch
    10. Public Exposure / Reputation Risk
    11. Interpretive Ambiguity / Polysemy
    12. Tone / Certainty Imbalance
    
    Attributes:
        id (int): Primary key
        proposition_id (int): Foreign key to propositions table
        
        needs_clarification (bool): Overall decision - should this be flagged?
        clarification_score (float): Aggregate score (0.0-1.0)
        
        factor_1_identity (float): Score for identity mismatch (0.0-1.0)
        factor_2_surveillance (float): Score for over-specific details (0.0-1.0)
        factor_3_intent (float): Score for inferred motives (0.0-1.0)
        factor_4_face_threat (float): Score for negative evaluation (0.0-1.0)
        factor_5_over_positive (float): Score for surprising praise (0.0-1.0)
        factor_6_opacity (float): Score for lack of evidence (0.0-1.0)
        factor_7_generalization (float): Score for absolutist language (0.0-1.0)
        factor_8_privacy (float): Score for sensitive domains (0.0-1.0)
        factor_9_actor_observer (float): Score for trait without context (0.0-1.0)
        factor_10_reputation (float): Score for reputation risk (0.0-1.0)
        factor_11_ambiguity (float): Score for interpretive ambiguity (0.0-1.0)
        factor_12_tone (float): Score for certainty imbalance (0.0-1.0)
        
        triggered_factors (dict): JSON list of factor names that triggered (score >= 0.6)
        reasoning_log (str): Natural language explanation of the analysis
        evidence_log (dict): JSON mapping of factors to their evidence citations
        llm_raw_output (dict): Full LLM response for debugging
        
        model_used (str): LLM model identifier (e.g., "gpt-4-turbo")
        prompt_version (str): Version of the detection prompt used
        validation_passed (bool): Whether the LLM output passed validation checks
        created_at (datetime): When the analysis was performed
    """
    __tablename__ = "clarification_analyses"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    proposition_id: Mapped[int] = mapped_column(
        ForeignKey("propositions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True  # One analysis per proposition (latest)
    )
    
    # Overall decision
    needs_clarification: Mapped[bool] = mapped_column(Boolean, nullable=False)
    clarification_score: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Per-factor scores (all 12 factors, each 0.0-1.0)
    factor_1_identity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    factor_2_surveillance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    factor_3_intent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    factor_4_face_threat: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    factor_5_over_positive: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    factor_6_opacity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    factor_7_generalization: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    factor_8_privacy: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    factor_9_actor_observer: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    factor_10_reputation: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    factor_11_ambiguity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    factor_12_tone: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    
    # Detailed results (stored as JSON)
    triggered_factors: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    reasoning_log: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_log: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    llm_raw_output: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    
    # Metadata
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)
    validation_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    # Relationship back to proposition
    proposition: Mapped[Proposition] = relationship(
        "Proposition",
        backref="clarification_analysis"
    )
    
    def __repr__(self) -> str:
        """String representation of the analysis."""
        return (
            f"<ClarificationAnalysis(prop_id={self.proposition_id}, "
            f"score={self.clarification_score:.2f}, "
            f"needs_clarification={self.needs_clarification})>"
        )
    
    def get_factor_scores(self) -> dict[str, float]:
        """Return all 12 factor scores as a dictionary."""
        return {
            "identity_mismatch": self.factor_1_identity,
            "surveillance": self.factor_2_surveillance,
            "inferred_intent": self.factor_3_intent,
            "face_threat": self.factor_4_face_threat,
            "over_positive": self.factor_5_over_positive,
            "opacity": self.factor_6_opacity,
            "generalization": self.factor_7_generalization,
            "privacy": self.factor_8_privacy,
            "actor_observer": self.factor_9_actor_observer,
            "reputation_risk": self.factor_10_reputation,
            "ambiguity": self.factor_11_ambiguity,
            "tone_imbalance": self.factor_12_tone,
        }
    
    def get_top_factors(self, n: int = 3) -> list[tuple[str, float]]:
        """Return the top N factors by score."""
        scores = self.get_factor_scores()
        sorted_factors = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_factors[:n]

