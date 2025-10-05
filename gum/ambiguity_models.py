# ambiguity_models.py
"""
Database models for ambiguity detection and urgency assessment.
Extends GUM's core models with tables for storing interpretations, 
cluster analyses, entropy scores, and GATE clarification dialogues.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from enum import Enum

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Float,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .models import Base, Proposition


class UrgencyLevel(str, Enum):
    """Urgency levels for propositions requiring clarification."""
    URGENT = "URGENT"  # Needs immediate clarification (high ambiguity + low confidence)
    SOON = "SOON"      # Should clarify in near term (time-sensitive or moderate ambiguity)
    LATER = "LATER"    # Can defer clarification (low ambiguity or high confidence)


class AmbiguityAnalysis(Base):
    """Stores ambiguity analysis results for propositions.
    
    This model captures the full ambiguity detection pipeline output:
    - Generated interpretations (distinct meanings)
    - Collected answers per interpretation
    - Semantic clusters of answers
    - Entropy score (ambiguity metric)
    - Binary ambiguity classification
    
    Attributes:
        id (int): Primary key.
        proposition_id (int): FK to the proposition being analyzed.
        interpretations (JSON): List of generated interpretations with distinguishing features.
        num_interpretations (int): Count of distinct interpretations.
        answers (JSON): Collected answers grouped by interpretation.
        clusters (JSON): Cluster assignments and sizes from semantic clustering.
        num_clusters (int): Number of distinct semantic clusters found.
        entropy_score (float): Shannon entropy over cluster distribution (0=unambiguous, higher=more ambiguous).
        is_ambiguous (bool): Binary classification based on entropy threshold.
        threshold_used (float): Entropy threshold applied for classification.
        created_at (datetime): When analysis was performed.
        model_used (str): LLM model used for generation.
        config (JSON): Analysis configuration (temperatures, num_samples, etc).
    """
    __tablename__ = "ambiguity_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    proposition_id: Mapped[int] = mapped_column(
        ForeignKey("propositions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Interpretation generation
    interpretations: Mapped[dict] = mapped_column(JSON, nullable=False)
    num_interpretations: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Answer collection
    answers: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # Clustering results
    clusters: Mapped[dict] = mapped_column(JSON, nullable=False)
    num_clusters: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Ambiguity metrics
    entropy_score: Mapped[float] = mapped_column(Float, nullable=False)
    is_ambiguous: Mapped[bool] = mapped_column(nullable=False)
    threshold_used: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=True)
    
    # Relationships
    proposition: Mapped[Proposition] = relationship(
        "Proposition",
        backref="ambiguity_analyses"
    )
    urgency_assessment: Mapped[Optional["UrgencyAssessment"]] = relationship(
        "UrgencyAssessment",
        back_populates="ambiguity_analysis",
        uselist=False
    )

    def __repr__(self) -> str:
        return f"<AmbiguityAnalysis(prop_id={self.proposition_id}, entropy={self.entropy_score:.2f}, ambiguous={self.is_ambiguous})>"


class UrgencyAssessment(Base):
    """Stores urgency assessment for ambiguous propositions.
    
    This model determines when to initiate GATE clarification dialogues
    based on ambiguity, confidence, and temporal factors.
    
    Attributes:
        id (int): Primary key.
        proposition_id (int): FK to the proposition.
        ambiguity_analysis_id (int): FK to the associated ambiguity analysis.
        urgency_level (UrgencyLevel): URGENT, SOON, or LATER.
        urgency_score (float): Continuous score (0-1) for ranking.
        reasoning (str): Explanation of why this urgency was assigned.
        time_sensitive (bool): Whether proposition involves time-sensitive context.
        confidence_factor (float): Contribution from GUM's confidence score.
        ambiguity_factor (float): Contribution from entropy score.
        temporal_keywords (List[str]): Detected time-related keywords.
        should_clarify_by (datetime): Recommended deadline for clarification.
        created_at (datetime): When assessment was made.
    """
    __tablename__ = "urgency_assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    proposition_id: Mapped[int] = mapped_column(
        ForeignKey("propositions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True  # One urgency assessment per proposition
    )
    ambiguity_analysis_id: Mapped[int] = mapped_column(
        ForeignKey("ambiguity_analyses.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Urgency classification
    urgency_level: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    urgency_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0-1 continuous
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Factors
    time_sensitive: Mapped[bool] = mapped_column(nullable=False)
    confidence_factor: Mapped[float] = mapped_column(Float, nullable=False)
    ambiguity_factor: Mapped[float] = mapped_column(Float, nullable=False)
    temporal_keywords: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Recommendation
    should_clarify_by: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    # Relationships
    proposition: Mapped[Proposition] = relationship(
        "Proposition",
        backref="urgency_assessment"
    )
    ambiguity_analysis: Mapped[AmbiguityAnalysis] = relationship(
        "AmbiguityAnalysis",
        back_populates="urgency_assessment"
    )
    clarification_dialogues: Mapped[List["ClarificationDialogue"]] = relationship(
        "ClarificationDialogue",
        back_populates="urgency_assessment",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<UrgencyAssessment(prop_id={self.proposition_id}, level={self.urgency_level}, score={self.urgency_score:.2f})>"


class ClarificationDialogue(Base):
    """Stores GATE clarification questions and user responses.
    
    This model tracks the dialogue state when asking users to clarify
    ambiguous propositions. Supports multi-turn conversations.
    
    Attributes:
        id (int): Primary key.
        urgency_assessment_id (int): FK to urgency assessment that triggered this.
        proposition_id (int): FK to the proposition being clarified.
        question_text (str): The clarifying question generated by GATE.
        question_type (str): Type of question (multiple_choice, yes_no, free_text).
        interpretations_context (JSON): Alternative interpretations presented to user.
        user_response (str): User's clarification response (nullable until answered).
        response_timestamp (datetime): When user responded.
        dialogue_state (str): PENDING, ANSWERED, SKIPPED, EXPIRED.
        follow_up_needed (bool): Whether additional clarification is needed.
        created_at (datetime): When question was generated.
        presented_at (datetime): When question was shown to user.
        expires_at (datetime): When this clarification request expires.
    """
    __tablename__ = "clarification_dialogues"

    id: Mapped[int] = mapped_column(primary_key=True)
    urgency_assessment_id: Mapped[int] = mapped_column(
        ForeignKey("urgency_assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    proposition_id: Mapped[int] = mapped_column(
        ForeignKey("propositions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Question content
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(50), nullable=False)
    interpretations_context: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # User response
    user_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Dialogue state
    dialogue_state: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDING",
        index=True
    )
    follow_up_needed: Mapped[bool] = mapped_column(nullable=False, default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    presented_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Relationships
    urgency_assessment: Mapped[UrgencyAssessment] = relationship(
        "UrgencyAssessment",
        back_populates="clarification_dialogues"
    )
    proposition: Mapped[Proposition] = relationship(
        "Proposition",
        backref="clarification_dialogues"
    )

    def __repr__(self) -> str:
        return f"<ClarificationDialogue(id={self.id}, prop_id={self.proposition_id}, state={self.dialogue_state})>"
