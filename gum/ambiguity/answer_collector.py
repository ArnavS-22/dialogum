# answer_collector.py
"""
Collects multiple LLM-generated answers for each interpretation.
Uses varied sampling to capture semantic diversity for clustering.
"""

import os
import asyncio
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from openai import OpenAI, AsyncOpenAI
from dotenv import load_dotenv

from ..ambiguity_config import AnswerCollectionConfig, DEFAULT_CONFIG
from .interpretation_generator import Interpretation

load_dotenv()


@dataclass
class Answer:
    """A single answer generated for an interpretation.
    
    Attributes:
        text: The answer text.
        interpretation_index: Which interpretation this answers.
        sample_number: Sample number (1 to N).
        metadata: Generation metadata (tokens, model, etc).
    """
    text: str
    interpretation_index: int
    sample_number: int
    metadata: Optional[Dict] = None


class AnswerCollector:
    """Collects multiple answers per interpretation using LLM sampling."""
    
    # System prompt for answer generation
    SYSTEM_PROMPT = """You are evaluating interpretations of user behavior propositions.

For each interpretation, provide a brief assessment of whether it accurately represents 
the user's behavior based on the available evidence.

Your response should be:
- Concise (1-2 sentences)
- Direct (yes/no or partially)
- Evidence-based (reference the reasoning provided)

Focus on semantic meaning, not exact wording."""

    def __init__(
        self,
        config: Optional[AnswerCollectionConfig] = None,
        api_key: Optional[str] = None
    ):
        """Initialize the answer collector.
        
        Args:
            config: Configuration for answer collection.
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var).
        """
        self.config = config or DEFAULT_CONFIG.answer_collection
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            raise ValueError("OpenAI API key required (set OPENAI_API_KEY env var)")
        
        self.client = OpenAI(api_key=self.api_key)
        self.async_client = AsyncOpenAI(api_key=self.api_key)
    
    def _build_user_prompt(
        self,
        interpretation: Interpretation,
        proposition_text: str,
        reasoning: str
    ) -> str:
        """Build prompt for answer generation.
        
        Args:
            interpretation: The interpretation to evaluate.
            proposition_text: Original proposition.
            reasoning: GUM's reasoning.
            
        Returns:
            Formatted user prompt.
        """
        prompt = f"""Original Proposition: "{proposition_text}"

GUM's Reasoning: "{reasoning}"

Interpretation to Evaluate: "{interpretation.text}"

Distinguishing Feature: {interpretation.distinguishing_feature}

Question: Does this interpretation accurately represent the user's behavior based on the evidence?

Provide a brief answer (1-2 sentences) indicating yes, no, or partially, with reasoning."""
        
        return prompt
    
    async def _generate_single_answer_async(
        self,
        interpretation: Interpretation,
        proposition_text: str,
        reasoning: str,
        interpretation_index: int,
        sample_number: int
    ) -> Answer:
        """Generate a single answer asynchronously.
        
        Args:
            interpretation: The interpretation to evaluate.
            proposition_text: Original proposition.
            reasoning: GUM's reasoning.
            interpretation_index: Index of this interpretation.
            sample_number: Sample number for this answer.
            
        Returns:
            Answer object.
        """
        user_prompt = self._build_user_prompt(interpretation, proposition_text, reasoning)
        
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
            
            answer_text = response.choices[0].message.content.strip()
            
            metadata = {
                "model": self.config.model,
                "temperature": self.config.temperature,
                "tokens_used": response.usage.total_tokens if response.usage else None,
                "success": True
            }
            
            return Answer(
                text=answer_text,
                interpretation_index=interpretation_index,
                sample_number=sample_number,
                metadata=metadata
            )
            
        except Exception as e:
            # Return error answer
            metadata = {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
            
            return Answer(
                text=f"[ERROR: {str(e)}]",
                interpretation_index=interpretation_index,
                sample_number=sample_number,
                metadata=metadata
            )
    
    async def collect_answers_async(
        self,
        interpretations: List[Interpretation],
        proposition_text: str,
        reasoning: str,
        num_answers_per_interpretation: Optional[int] = None
    ) -> Tuple[List[Answer], Dict]:
        """Collect multiple answers for all interpretations asynchronously.
        
        Args:
            interpretations: List of interpretations to evaluate.
            proposition_text: Original proposition.
            reasoning: GUM's reasoning.
            num_answers_per_interpretation: Override config default.
            
        Returns:
            Tuple of (list of Answer objects, metadata dict).
        """
        num_answers = num_answers_per_interpretation or self.config.num_answers_per_interpretation
        
        if not interpretations:
            return [], {"success": False, "error": "No interpretations provided"}
        
        # Create tasks for all answers
        tasks = []
        for interp_idx, interpretation in enumerate(interpretations):
            for sample_num in range(1, num_answers + 1):
                task = self._generate_single_answer_async(
                    interpretation=interpretation,
                    proposition_text=proposition_text,
                    reasoning=reasoning,
                    interpretation_index=interp_idx,
                    sample_number=sample_num
                )
                tasks.append(task)
        
        # Execute all tasks concurrently
        answers = await asyncio.gather(*tasks)
        
        # Compile metadata
        total_answers = len(answers)
        successful_answers = sum(1 for a in answers if a.metadata and a.metadata.get("success", False))
        failed_answers = total_answers - successful_answers
        
        total_tokens = sum(
            a.metadata.get("tokens_used", 0) 
            for a in answers 
            if a.metadata and a.metadata.get("tokens_used")
        )
        
        metadata = {
            "num_interpretations": len(interpretations),
            "answers_per_interpretation": num_answers,
            "total_answers_requested": total_answers,
            "successful_answers": successful_answers,
            "failed_answers": failed_answers,
            "total_tokens_used": total_tokens,
            "success": failed_answers == 0
        }
        
        return answers, metadata
    
    def collect_answers(
        self,
        interpretations: List[Interpretation],
        proposition_text: str,
        reasoning: str,
        num_answers_per_interpretation: Optional[int] = None
    ) -> Tuple[List[Answer], Dict]:
        """Collect multiple answers for all interpretations (synchronous wrapper).
        
        Args:
            interpretations: List of interpretations to evaluate.
            proposition_text: Original proposition.
            reasoning: GUM's reasoning.
            num_answers_per_interpretation: Override config default.
            
        Returns:
            Tuple of (list of Answer objects, metadata dict).
        """
        return asyncio.run(
            self.collect_answers_async(
                interpretations,
                proposition_text,
                reasoning,
                num_answers_per_interpretation
            )
        )


def format_answers_for_storage(answers: List[Answer]) -> Dict:
    """Convert answers to JSON-serializable dict for database storage.
    
    Args:
        answers: List of Answer objects.
        
    Returns:
        Dict suitable for JSON storage, grouped by interpretation.
    """
    # Group answers by interpretation
    grouped = {}
    for answer in answers:
        interp_idx = answer.interpretation_index
        if interp_idx not in grouped:
            grouped[interp_idx] = []
        
        grouped[interp_idx].append({
            "text": answer.text,
            "sample_number": answer.sample_number,
            "success": answer.metadata.get("success", False) if answer.metadata else False
        })
    
    return {
        "answers_by_interpretation": grouped,
        "total_answers": len(answers),
        "num_interpretations": len(grouped)
    }


def get_answer_texts(answers: List[Answer]) -> List[str]:
    """Extract just the text from answers for clustering.
    
    Args:
        answers: List of Answer objects.
        
    Returns:
        List of answer text strings (excludes error answers).
    """
    return [
        answer.text 
        for answer in answers 
        if answer.metadata 
        and answer.metadata.get("success", False)
        and not answer.text.startswith("[ERROR:")
    ]
