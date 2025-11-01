"""
Core generation logic for clarifying questions.

This module provides:
- QuestionGenerator class with two methods: few-shot and controlled QG
- Evidence extraction from observations
- Retry logic with validation
"""

import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI

from .question_config import (
    get_method_for_factor,
    get_factor_name,
    get_factor_id_from_name,
    MAX_GENERATION_RETRIES,
    MAX_EVIDENCE_ITEMS
)
from .question_prompts import (
    build_few_shot_prompt,
    build_controlled_qg_prompt,
    format_observation_summary
)
from .question_validator import QuestionValidator

logger = logging.getLogger(__name__)


class QuestionGenerator:
    """Generates clarifying questions using few-shot or controlled QG methods."""
    
    def __init__(
        self,
        openai_client: AsyncOpenAI,
        model: str = "gpt-4o",  # gpt-4o supports JSON mode
        temperature: float = 0.7,
        max_tokens: int = 300
    ):
        """
        Initialize question generator.
        
        Args:
            openai_client: AsyncOpenAI client
            model: Model name to use
            temperature: Sampling temperature
            max_tokens: Max tokens for generation
        """
        self.client = openai_client
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.validator = QuestionValidator()
    
    async def generate_question_pair(
        self,
        prop_id: int,
        prop_text: str,
        factor_id: int,
        observations: List[Any],
        prop_reasoning: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main entry point: generates question + reasoning + evidence.
        
        Args:
            prop_id: Proposition ID
            prop_text: Proposition text
            factor_id: Factor ID (1-12)
            observations: List of Observation objects or dicts
            prop_reasoning: Optional reasoning from proposition generation
            
        Returns:
            Dict with:
            - prop_id: int
            - factor: str (factor name)
            - question: str
            - reasoning: str
            - evidence: List[str]
            
        Raises:
            Exception: If generation fails after retries
        """
        method = get_method_for_factor(factor_id)
        factor_name = get_factor_name(factor_id)
        
        logger.info(f"Generating question for prop {prop_id}, factor {factor_name} using {method}")
        
        try:
            if method == "few_shot":
                result = await self._generate_from_few_shot(
                    prop_id, prop_text, factor_id, observations, prop_reasoning
                )
            elif method == "controlled_qg":
                result = await self._generate_from_controlled_qg(
                    prop_id, prop_text, factor_id, observations
                )
            else:
                raise ValueError(f"Unknown method: {method}")
            
            # Add factor name to result
            result["factor"] = factor_name
            result["prop_id"] = prop_id
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to generate question for prop {prop_id}, factor {factor_name}: {e}")
            raise
    
    async def _generate_from_few_shot(
        self,
        prop_id: int,
        prop_text: str,
        factor_id: int,
        observations: List[Any],
        prop_reasoning: Optional[str]
    ) -> Dict[str, Any]:
        """
        Generate using few-shot LLM prompt.
        
        Steps:
        1. Build few-shot prompt with examples
        2. Call LLM with JSON response format
        3. Parse JSON (question, reasoning)
        4. Extract evidence
        5. Return dict
        
        Args:
            prop_id: Proposition ID
            prop_text: Proposition text
            factor_id: Factor ID
            observations: List of observations
            prop_reasoning: Optional proposition reasoning
            
        Returns:
            Dict with question, reasoning, evidence
        """
        observation_summary = format_observation_summary(observations)
        system_prompt, user_prompt = build_few_shot_prompt(
            prop_text, factor_id, observation_summary
        )
        
        # Call LLM
        response = await self._call_llm(system_prompt, user_prompt)
        
        # Parse response
        parsed = self._parse_json_response(response)
        
        # Extract evidence
        evidence = self._extract_evidence(observations, factor_id)
        
        result = {
            "question": parsed["question"],
            "reasoning": parsed["reasoning"],
            "evidence": evidence
        }
        
        return result
    
    async def _generate_from_controlled_qg(
        self,
        prop_id: int,
        prop_text: str,
        factor_id: int,
        observations: List[Any],
        max_retries: int = None
    ) -> Dict[str, Any]:
        """
        Generate using controlled QG (polite prompt + validation).
        
        Steps:
        1. Build controlled QG prompt
        2. Call LLM with JSON response format
        3. Parse JSON (question, reasoning)
        4. Run validation checks
        5. If validation fails, retry with adjusted prompt (max retries)
        6. Extract evidence
        7. Return dict
        
        Args:
            prop_id: Proposition ID
            prop_text: Proposition text
            factor_id: Factor ID
            observations: List of observations
            max_retries: Maximum retry attempts
            
        Returns:
            Dict with question, reasoning, evidence
        """
        if max_retries is None:
            max_retries = MAX_GENERATION_RETRIES
        
        observation_summary = format_observation_summary(observations)
        validation_feedback = ""
        
        for attempt in range(max_retries + 1):
            try:
                # Build prompt
                system_prompt, user_prompt = build_controlled_qg_prompt(
                    prop_text, factor_id, observation_summary, validation_feedback
                )
                
                # Call LLM
                response = await self._call_llm(system_prompt, user_prompt)
                
                # Parse response
                parsed = self._parse_json_response(response)
                
                # Validate
                is_valid, errors = self.validator.validate_full_output({
                    "question": parsed["question"],
                    "reasoning": parsed["reasoning"],
                    "factor": get_factor_name(factor_id),
                    "prop_id": prop_id
                })
                
                if is_valid or attempt == max_retries:
                    # Success or last attempt - use what we have
                    if not is_valid:
                        logger.warning(f"Final attempt for prop {prop_id} still has validation errors: {errors}")
                        # Truncate reasoning if too long
                        if "Reasoning: " in str(errors):
                            parsed["reasoning"] = self.validator.truncate_reasoning(parsed["reasoning"])
                    
                    # Extract evidence
                    evidence = self._extract_evidence(observations, factor_id)
                    
                    result = {
                        "question": parsed["question"],
                        "reasoning": parsed["reasoning"],
                        "evidence": evidence
                    }
                    
                    return result
                else:
                    # Retry with feedback
                    validation_feedback = self.validator.get_validation_feedback(errors)
                    logger.info(f"Retrying generation for prop {prop_id} (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(0.5)  # Brief delay between retries
                    
            except Exception as e:
                if attempt == max_retries:
                    raise
                logger.warning(f"Attempt {attempt + 1} failed for prop {prop_id}: {e}")
                await asyncio.sleep(0.5)
        
        # Should not reach here
        raise RuntimeError(f"Failed to generate valid question after {max_retries} retries")
    
    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """
        Call LLM with retry logic.
        
        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            
        Returns:
            Response text
        """
        max_api_retries = 3
        
        for attempt in range(max_api_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    response_format={"type": "json_object"}
                )
                
                return response.choices[0].message.content
                
            except Exception as e:
                if attempt == max_api_retries - 1:
                    logger.error(f"API call failed after {max_api_retries} attempts: {e}")
                    raise
                
                # Exponential backoff
                wait_time = 2 ** attempt
                logger.warning(f"API call failed (attempt {attempt + 1}/{max_api_retries}), retrying in {wait_time}s: {e}")
                await asyncio.sleep(wait_time)
        
        raise RuntimeError("Should not reach here")
    
    def _parse_json_response(self, response: str) -> Dict[str, str]:
        """
        Parse JSON response from LLM.
        
        Args:
            response: Response text
            
        Returns:
            Dict with question and reasoning
            
        Raises:
            ValueError: If response is not valid JSON or missing fields
        """
        try:
            parsed = json.loads(response)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {e}\nResponse: {response}")
        
        if "question" not in parsed:
            raise ValueError(f"Response missing 'question' field: {parsed}")
        
        if "reasoning" not in parsed:
            raise ValueError(f"Response missing 'reasoning' field: {parsed}")
        
        return {
            "question": parsed["question"].strip(),
            "reasoning": parsed["reasoning"].strip()
        }
    
    def _extract_evidence(
        self,
        observations: List[Any],
        factor_id: int,
        limit: int = None
    ) -> List[str]:
        """
        Extract evidence citations from observations.
        
        Args:
            observations: List of observation objects or dicts
            factor_id: Factor ID (for context)
            limit: Max number of evidence items (default: MAX_EVIDENCE_ITEMS)
            
        Returns:
            List of evidence strings in format "obs_{id}: {summary}"
        """
        if limit is None:
            limit = MAX_EVIDENCE_ITEMS
        
        if not observations:
            return []
        
        evidence = []
        
        for obs in observations[:limit]:
            # Handle both dict and object formats
            if isinstance(obs, dict):
                obs_id = obs.get('id', 'unknown')
                obs_text = obs.get('observation_text', obs.get('text', ''))
            else:
                obs_id = getattr(obs, 'id', 'unknown')
                obs_text = getattr(obs, 'observation_text', '')
            
            # Truncate long observations
            if len(obs_text) > 100:
                obs_text = obs_text[:100] + "..."
            
            evidence.append(f"obs_{obs_id}: {obs_text}")
        
        return evidence


class BatchQuestionGenerator:
    """Batch generation with concurrency control."""
    
    def __init__(
        self,
        openai_client: AsyncOpenAI,
        model: str = "gpt-4",
        max_concurrent: int = 5
    ):
        """
        Initialize batch generator.
        
        Args:
            openai_client: AsyncOpenAI client
            model: Model name
            max_concurrent: Max concurrent generations
        """
        self.generator = QuestionGenerator(openai_client, model)
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def generate_batch(
        self,
        items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Generate questions for a batch of items concurrently.
        
        Args:
            items: List of dicts with prop_id, prop_text, factor_id, observations
            
        Returns:
            List of result dicts (same order as input)
        """
        tasks = [self._generate_with_semaphore(item) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error dicts
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch item {i} failed: {result}")
                processed_results.append({
                    "error": str(result),
                    "prop_id": items[i].get("prop_id"),
                    "factor": items[i].get("factor_id")
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _generate_with_semaphore(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Generate with semaphore for concurrency control."""
        async with self.semaphore:
            return await self.generator.generate_question_pair(
                prop_id=item["prop_id"],
                prop_text=item["prop_text"],
                factor_id=item["factor_id"],
                observations=item["observations"],
                prop_reasoning=item.get("prop_reasoning")
            )

