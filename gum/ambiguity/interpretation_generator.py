# interpretation_generator.py
"""
Generates distinct interpretations of user behavior propositions.
Adapted from UCSB's clarification generation approach.
"""

import os
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import asyncio

from openai import OpenAI, AsyncOpenAI
from dotenv import load_dotenv

from ..ambiguity_config import InterpretationConfig, DEFAULT_CONFIG

# Load environment variables
load_dotenv()


@dataclass
class Interpretation:
    """A single interpretation of a proposition.
    
    Attributes:
        text: The specific, concrete interpretation statement.
        distinguishing_feature: What makes this interpretation distinct.
        confidence: Optional confidence score for this interpretation.
    """
    text: str
    distinguishing_feature: str
    confidence: Optional[float] = None


class InterpretationGenerator:
    """Generates multiple distinct interpretations for ambiguous propositions."""
    
    # System prompt adapted from UCSB's approach
    SYSTEM_PROMPT = """You are analyzing propositions about user behavior that were inferred from observations.
These propositions may be ambiguous - they could mean different things.

Your job: Generate 2-4 DISTINCT interpretations of what the proposition could mean.

Each interpretation must:
1. Be a specific, concrete statement (not vague)
2. Be meaningfully different from other interpretations (not just reworded)
3. Explain what makes this interpretation distinct

Common sources of ambiguity in user behavior:
- Scope: narrow vs broad (e.g., "uses Python" = for specific tasks vs generally)
- Context: what situation (e.g., "reads articles" = for work vs leisure vs learning)
- Temporal: currently vs historically vs planning to
- Intensity: strong preference vs casual interest vs exploratory
- Purpose: doing for work vs personal interest vs learning
- User identity: who exactly (e.g., "user" = individual, team, organization)

Format your response EXACTLY as:
Interpretation 1: [specific statement]
Distinguishing feature: [what makes this different]

Interpretation 2: [specific statement]
Distinguishing feature: [what makes this different]

Interpretation 3: [specific statement]
Distinguishing feature: [what makes this different]

If the proposition is already completely clear and unambiguous, output:
"No ambiguity detected - single clear interpretation"
"""
    
    def __init__(
        self,
        config: Optional[InterpretationConfig] = None,
        api_key: Optional[str] = None
    ):
        """Initialize the interpretation generator.
        
        Args:
            config: Configuration for interpretation generation.
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var).
        """
        self.config = config or DEFAULT_CONFIG.interpretation
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            raise ValueError("OpenAI API key required (set OPENAI_API_KEY env var)")
        
        self.client = OpenAI(api_key=self.api_key)
        self.async_client = AsyncOpenAI(api_key=self.api_key)
    
    def _build_user_prompt(
        self,
        proposition_text: str,
        reasoning: str,
        confidence: Optional[int] = None,
        observations_summary: Optional[str] = None
    ) -> str:
        """Build the user prompt for interpretation generation.
        
        Args:
            proposition_text: The proposition to interpret.
            reasoning: GUM's reasoning for the proposition.
            confidence: GUM's confidence score (1-10).
            observations_summary: Optional summary of observations.
            
        Returns:
            Formatted user prompt.
        """
        prompt_parts = [
            f'Proposition: "{proposition_text}"',
            f'How this was inferred: "{reasoning}"'
        ]
        
        if confidence is not None:
            prompt_parts.append(f"GUM's confidence: {confidence}/10")
        
        if observations_summary:
            prompt_parts.append(f"Observation context: {observations_summary}")
        
        prompt_parts.append("\nGenerate 2-4 distinct interpretations of what this proposition could mean.")
        
        return "\n\n".join(prompt_parts)
    
    def _parse_interpretations(self, response_text: str) -> List[Interpretation]:
        """Parse LLM response into structured interpretations.
        
        Args:
            response_text: Raw LLM response.
            
        Returns:
            List of Interpretation objects.
        """
        # Check for unambiguous case
        if "no ambiguity detected" in response_text.lower():
            return []
        
        interpretations = []
        
        # Pattern: "Interpretation N: <text>\nDistinguishing feature: <feature>"
        pattern = r'Interpretation \d+:\s*(.+?)\n\s*Distinguishing feature:\s*(.+?)(?=\n\nInterpretation \d+:|$)'
        
        matches = re.findall(pattern, response_text, re.DOTALL | re.IGNORECASE)
        
        for text, feature in matches:
            interpretations.append(Interpretation(
                text=text.strip(),
                distinguishing_feature=feature.strip()
            ))
        
        return interpretations
    
    def generate(
        self,
        proposition_text: str,
        reasoning: str,
        confidence: Optional[int] = None,
        observations_summary: Optional[str] = None
    ) -> Tuple[List[Interpretation], Dict]:
        """Generate interpretations for a proposition (synchronous).
        
        Args:
            proposition_text: The proposition to interpret.
            reasoning: GUM's reasoning for the proposition.
            confidence: GUM's confidence score (1-10).
            observations_summary: Optional summary of observations.
            
        Returns:
            Tuple of (interpretations list, metadata dict).
        """
        user_prompt = self._build_user_prompt(
            proposition_text,
            reasoning,
            confidence,
            observations_summary
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                timeout=self.config.timeout_seconds
            )
            
            response_text = response.choices[0].message.content
            interpretations = self._parse_interpretations(response_text)
            
            metadata = {
                "model": self.config.model,
                "temperature": self.config.temperature,
                "tokens_used": response.usage.total_tokens if response.usage else None,
                "raw_response": response_text,
                "success": True,
                "error": None
            }
            
            # Validate interpretation count
            if len(interpretations) < self.config.min_interpretations:
                metadata["warning"] = f"Generated {len(interpretations)} interpretations (min: {self.config.min_interpretations})"
            
            return interpretations, metadata
            
        except Exception as e:
            # Return empty list with error metadata
            metadata = {
                "model": self.config.model,
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
            return [], metadata
    
    async def generate_async(
        self,
        proposition_text: str,
        reasoning: str,
        confidence: Optional[int] = None,
        observations_summary: Optional[str] = None
    ) -> Tuple[List[Interpretation], Dict]:
        """Generate interpretations for a proposition (asynchronous).
        
        Args:
            proposition_text: The proposition to interpret.
            reasoning: GUM's reasoning for the proposition.
            confidence: GUM's confidence score (1-10).
            observations_summary: Optional summary of observations.
            
        Returns:
            Tuple of (interpretations list, metadata dict).
        """
        user_prompt = self._build_user_prompt(
            proposition_text,
            reasoning,
            confidence,
            observations_summary
        )
        
        try:
            response = await self.async_client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                timeout=self.config.timeout_seconds
            )
            
            response_text = response.choices[0].message.content
            interpretations = self._parse_interpretations(response_text)
            
            metadata = {
                "model": self.config.model,
                "temperature": self.config.temperature,
                "tokens_used": response.usage.total_tokens if response.usage else None,
                "raw_response": response_text,
                "success": True,
                "error": None
            }
            
            # Validate interpretation count
            if len(interpretations) < self.config.min_interpretations:
                metadata["warning"] = f"Generated {len(interpretations)} interpretations (min: {self.config.min_interpretations})"
            
            return interpretations, metadata
            
        except Exception as e:
            metadata = {
                "model": self.config.model,
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
            return [], metadata
    
    async def generate_batch_async(
        self,
        propositions: List[Dict]
    ) -> List[Tuple[List[Interpretation], Dict]]:
        """Generate interpretations for multiple propositions concurrently.
        
        Args:
            propositions: List of dicts with keys: text, reasoning, confidence.
            
        Returns:
            List of (interpretations, metadata) tuples, one per proposition.
        """
        tasks = [
            self.generate_async(
                proposition_text=prop["text"],
                reasoning=prop["reasoning"],
                confidence=prop.get("confidence"),
                observations_summary=prop.get("observations_summary")
            )
            for prop in propositions
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions in batch
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                metadata = {
                    "success": False,
                    "error": str(result),
                    "error_type": type(result).__name__
                }
                processed_results.append(([], metadata))
            else:
                processed_results.append(result)
        
        return processed_results


def format_interpretations_for_storage(interpretations: List[Interpretation]) -> Dict:
    """Convert interpretations to JSON-serializable dict for database storage.
    
    Args:
        interpretations: List of Interpretation objects.
        
    Returns:
        Dict suitable for JSON storage.
    """
    return {
        "interpretations": [
            {
                "text": interp.text,
                "distinguishing_feature": interp.distinguishing_feature,
                "confidence": interp.confidence
            }
            for interp in interpretations
        ],
        "count": len(interpretations)
    }
