# detector.py
"""
ClarificationDetector - Main detection engine for analyzing propositions.

This module implements the core logic for detecting when propositions should
be flagged for clarifying dialogue through Gates.
"""

import json
import logging
from typing import Dict, List, Any, Optional

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models import Proposition, Observation
from ..db_utils import get_related_observations
from ..clarification_models import ClarificationAnalysis
from .prompts import CLARIFICATION_ANALYSIS_PROMPT, PROMPT_VERSION

logger = logging.getLogger(__name__)


class ClarificationDetector:
    """
    Analyzes propositions against 12 psychological factors to determine
    if they should be flagged for clarifying dialogue.
    
    The detector:
    1. Builds context from proposition + observations
    2. Calls LLM with comprehensive prompt
    3. Validates the LLM response
    4. Persists the analysis to database
    
    Attributes:
        client (AsyncOpenAI): OpenAI client for LLM calls
        config: Configuration object with model, temperature, etc.
        prompt_version (str): Version of the detection prompt being used
    """
    
    def __init__(self, openai_client: AsyncOpenAI, config):
        """
        Initialize the detector.
        
        Args:
            openai_client: Async OpenAI client for making LLM calls
            config: Configuration object (should have clarification settings)
        """
        self.client = openai_client
        self.config = config
        self.prompt_version = PROMPT_VERSION
        
        # Get clarification-specific config if available
        if hasattr(config, 'clarification'):
            self.clarification_config = config.clarification
        else:
            # Use defaults
            from dataclasses import dataclass
            @dataclass
            class DefaultConfig:
                model: str = "gpt-4-turbo"
                temperature: float = 0.1
                threshold: float = 0.6
            self.clarification_config = DefaultConfig()
    
    async def analyze(
        self, 
        proposition: Proposition, 
        session: AsyncSession
    ) -> ClarificationAnalysis:
        """
        Main detection pipeline - analyzes a proposition and returns results.
        
        Args:
            proposition: The proposition to analyze
            session: Database session for loading observations and persisting results
            
        Returns:
            ClarificationAnalysis object with scores and decision
        """
        logger.info(f"Analyzing proposition {proposition.id}: {proposition.text[:100]}...")
        
        try:
            # 1. Build context from proposition + observations
            context = await self._build_context(proposition, session)
            
            # 2. Call LLM
            llm_response = await self._call_llm(context)
            
            # 3. Validate response
            validation_result = self._validate_response(llm_response, context)
            
            # 4. Create analysis record
            analysis = self._create_analysis(
                proposition.id,
                llm_response,
                validation_result
            )
            
            # 5. Persist to database
            session.add(analysis)
            await session.flush()  # Get the ID without committing
            
            logger.info(
                f"Analysis complete for prop {proposition.id}: "
                f"score={analysis.clarification_score:.2f}, "
                f"needs_clarification={analysis.needs_clarification}"
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing proposition {proposition.id}: {e}")
            # Create a failed analysis record
            return self._create_error_analysis(proposition.id, str(e))
    
    async def _build_context(
        self, 
        proposition: Proposition, 
        session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Build the context dictionary for the LLM prompt.
        
        Args:
            proposition: The proposition to analyze
            session: Database session for loading observations
            
        Returns:
            Dictionary with all context fields for the prompt
        """
        # Load related observations (increased from default 5 to 20 for better context)
        observations = await get_related_observations(session, proposition.id, limit=20)
        
        # Extract user name from proposition text
        user_name = self._extract_user_name(proposition.text)
        
        # Format observations for the prompt
        observations_text = self._format_observations(observations)
        
        context = {
            "user_name": user_name,
            "proposition_text": proposition.text,
            "reasoning": proposition.reasoning or "No reasoning provided",
            "confidence": proposition.confidence if proposition.confidence is not None else 5,
            "observations": observations_text,
            "observation_ids": [obs.id for obs in observations]
        }
        
        return context
    
    def _extract_user_name(self, text: str) -> str:
        """Extract user name from proposition text."""
        # Simple heuristic: look for first capitalized name
        words = text.split()
        for i, word in enumerate(words[:5]):  # Check first 5 words
            if word[0].isupper() and len(word) > 2:
                # Check if next word is also capitalized (last name)
                if i + 1 < len(words) and words[i+1][0].isupper():
                    return f"{word} {words[i+1]}"
                return word
        return "the user"
    
    def _format_observations(self, observations: List[Observation]) -> str:
        """Format observations for inclusion in the prompt."""
        if not observations:
            return "No observations available."
        
        formatted = []
        for i, obs in enumerate(observations[:10], 1):  # Limit to 10 most recent
            # Truncate long observations
            content = obs.content[:200] + "..." if len(obs.content) > 200 else obs.content
            formatted.append(
                f"[{i}] (ID: {obs.id}) {obs.observer_name}: {content}"
            )
        
        return "\n".join(formatted)
    
    async def _call_llm(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call the LLM with the comprehensive prompt.
        
        Args:
            context: Dictionary with all context fields
            
        Returns:
            Parsed JSON response from the LLM
        """
        # Format the prompt with context
        prompt = CLARIFICATION_ANALYSIS_PROMPT.format(**context)
        
        logger.debug(f"Calling LLM with model={self.clarification_config.model}")
        
        try:
            response = await self.client.chat.completions.create(
                model=self.clarification_config.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert in cognitive psychology analyzing behavioral propositions. Always return valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=self.clarification_config.temperature,
                response_format={"type": "json_object"}
            )
            
            # Parse JSON response
            content = response.choices[0].message.content
            parsed = json.loads(content)
            
            logger.debug(f"LLM response parsed successfully")
            return parsed
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            raise
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise
    
    def _validate_response(
        self, 
        llm_response: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate the LLM response for quality and consistency.
        
        Args:
            llm_response: The parsed LLM response
            context: The original context passed to the LLM
            
        Returns:
            Dictionary with validation results
        """
        validation = {
            "passed": True,
            "issues": [],
            "evidence_quality": "high"
        }
        
        # Check that we have all required fields
        if "factors" not in llm_response:
            validation["passed"] = False
            validation["issues"].append("Missing 'factors' field")
            return validation
        
        if "aggregate" not in llm_response:
            validation["passed"] = False
            validation["issues"].append("Missing 'aggregate' field")
            return validation
        
        # Check that we have all 12 factors
        factors = llm_response["factors"]
        if len(factors) != 12:
            validation["passed"] = False
            validation["issues"].append(f"Expected 12 factors, got {len(factors)}")
            return validation
        
        # Validate each factor
        for factor in factors:
            factor_id = factor.get("id")
            factor_name = factor.get("name")
            
            # Check required fields
            if "score" not in factor:
                validation["issues"].append(f"Factor {factor_id} missing score")
                validation["evidence_quality"] = "low"
                continue
            
            # Check if triggered factors have evidence
            if factor.get("triggered", False):
                evidence = factor.get("evidence", [])
                if not evidence or len(evidence) == 0:
                    validation["issues"].append(
                        f"Factor {factor_id} ({factor_name}) triggered but no evidence provided"
                    )
                    validation["evidence_quality"] = "low"
            
            # Verify observation IDs are valid (if cited)
            obs_ids_cited = factor.get("observation_ids_cited", [])
            valid_obs_ids = context.get("observation_ids", [])
            for obs_id in obs_ids_cited:
                if obs_id not in valid_obs_ids:
                    validation["issues"].append(
                        f"Factor {factor_id} cites invalid observation ID: {obs_id}"
                    )
                    validation["passed"] = False
        
        # Factor 7 specific validation: if triggered, must have absolutist words
        # Use defensive coding - don't crash if factor 7 is missing
        factor_7 = next((f for f in factors if f.get("id") == 7), None)
        if factor_7 and factor_7.get("triggered", False):
            absolutist_words = ["always", "never", "all", "every", "none", "invariably"]
            prop_text = context["proposition_text"].lower()
            if not any(word in prop_text for word in absolutist_words):
                validation["issues"].append(
                    "Factor 7 (generalization) triggered but no absolutist words found in text"
                )
                # Don't fail, but note the issue
                validation["evidence_quality"] = "medium"
        
        # Log validation results
        if validation["issues"]:
            logger.warning(f"Validation issues: {validation['issues']}")
        
        return validation
    
    def _create_analysis(
        self,
        proposition_id: int,
        llm_response: Dict[str, Any],
        validation_result: Dict[str, Any]
    ) -> ClarificationAnalysis:
        """
        Create a ClarificationAnalysis record from LLM response.
        
        Args:
            proposition_id: ID of the proposition analyzed
            llm_response: Parsed LLM response
            validation_result: Results from validation
            
        Returns:
            ClarificationAnalysis instance ready to be persisted
        """
        factors = llm_response["factors"]
        aggregate = llm_response["aggregate"]
        
        # Extract per-factor scores (in order 1-12)
        factor_scores = {f["id"]: f["score"] for f in factors}
        
        # Build triggered factors list
        triggered = [
            f["name"] for f in factors 
            if f.get("triggered", False)
        ]
        
        # Build evidence log
        evidence_log = {
            f["name"]: {
                "evidence": f.get("evidence", []),
                "reasoning": f.get("reasoning", ""),
                "observation_ids": f.get("observation_ids_cited", [])
            }
            for f in factors
        }
        
        # Create the analysis record
        analysis = ClarificationAnalysis(
            proposition_id=proposition_id,
            
            # Overall decision
            needs_clarification=aggregate.get("needs_clarification", False),
            clarification_score=aggregate.get("clarification_score", 0.0),
            
            # Per-factor scores
            factor_1_identity=factor_scores.get(1, 0.0),
            factor_2_surveillance=factor_scores.get(2, 0.0),
            factor_3_intent=factor_scores.get(3, 0.0),
            factor_4_face_threat=factor_scores.get(4, 0.0),
            factor_5_over_positive=factor_scores.get(5, 0.0),
            factor_6_opacity=factor_scores.get(6, 0.0),
            factor_7_generalization=factor_scores.get(7, 0.0),
            factor_8_privacy=factor_scores.get(8, 0.0),
            factor_9_actor_observer=factor_scores.get(9, 0.0),
            factor_10_reputation=factor_scores.get(10, 0.0),
            factor_11_ambiguity=factor_scores.get(11, 0.0),
            factor_12_tone=factor_scores.get(12, 0.0),
            
            # Detailed results
            triggered_factors={"factors": triggered},
            reasoning_log=aggregate.get("reasoning_summary", ""),
            evidence_log=evidence_log,
            llm_raw_output=llm_response,
            
            # Metadata
            model_used=self.clarification_config.model,
            prompt_version=self.prompt_version,
            validation_passed=validation_result["passed"]
        )
        
        return analysis
    
    def _create_error_analysis(
        self,
        proposition_id: int,
        error_message: str
    ) -> ClarificationAnalysis:
        """Create an analysis record for a failed analysis."""
        return ClarificationAnalysis(
            proposition_id=proposition_id,
            needs_clarification=False,
            clarification_score=0.0,
            reasoning_log=f"Analysis failed: {error_message}",
            model_used=self.clarification_config.model,
            prompt_version=self.prompt_version,
            validation_passed=False,
            llm_raw_output={"error": error_message},
            triggered_factors={},
            evidence_log={}
        )

