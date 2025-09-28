"""
Long-term memory generation service for GUM.

This service generates structured long-term memories from propositions using 
AI-powered clustering and generalization with strict JSON validation.
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel, ValidationError, Field

from .models import Proposition, LongTermMemory


class MemoryGenerationItem(BaseModel):
    """Pydantic model for strict validation of AI-generated memory items."""
    category: str = Field(..., pattern="^(workflow|preference|habit)$")
    generalization: str = Field(..., min_length=10, max_length=500)
    supporting_prop_ids: List[str] = Field(..., min_length=1, max_length=30)
    rationale: str = Field(..., min_length=20, max_length=1000)
    first_seen: str = Field(..., description="ISO timestamp of earliest prop")
    last_seen: str = Field(..., description="ISO timestamp of latest prop")
    tags: List[str] = Field(..., min_length=1, max_length=10)


class MemoryGenerationResponse(BaseModel):
    """Pydantic model for complete AI response validation."""
    user_id: str = Field(...)
    long_term_generalizations: List[MemoryGenerationItem] = Field(..., min_length=1, max_length=20)


@dataclass
class MemoryServiceConfig:
    """Configuration for memory service."""
    model: str = "gpt-4"
    temperature: float = 0.1
    max_tokens: int = 4000
    timeout_seconds: int = 60
    max_retries: int = 3


class LongTermMemoryService:
    """Service for generating long-term memories from propositions."""
    
    def __init__(self, 
                 openai_client: AsyncOpenAI, 
                 config: Optional[MemoryServiceConfig] = None,
                 logger: Optional[logging.Logger] = None):
        """Initialize the memory service.
        
        Args:
            openai_client: AsyncOpenAI client instance
            config: Service configuration
            logger: Logger instance
        """
        self.client = openai_client
        self.config = config or MemoryServiceConfig()
        self.logger = logger or logging.getLogger(__name__)

    async def fetch_last_30_propositions(self, session: AsyncSession) -> List[Proposition]:
        """Fetch the last 30 propositions ordered by creation time.
        
        Args:
            session: Database session
            
        Returns:
            List of up to 30 most recent propositions
        """
        try:
            result = await session.execute(
                select(Proposition)
                .order_by(desc(Proposition.created_at))
                .limit(30)
            )
            propositions = result.scalars().all()
            self.logger.info(f"Fetched {len(propositions)} propositions for memory generation")
            return list(propositions)
        except Exception as e:
            self.logger.error(f"Failed to fetch propositions: {e}")
            raise

    def build_memory_prompt(self, user_id: str, propositions: List[Proposition]) -> str:
        """Build the AI prompt for memory generation with strict JSON requirements.
        
        Args:
            user_id: User identifier
            propositions: List of propositions to analyze
            
        Returns:
            Formatted prompt string
        """
        # Convert propositions to prompt format
        prop_data = []
        for prop in propositions:
            prop_data.append({
                "id": str(prop.id),
                "timestamp": prop.created_at,
                "text": prop.text,
                "reasoning": prop.reasoning,
                "confidence": prop.confidence,
                "decay": prop.decay
            })

        return f"""You are tasked with creating a **long-term memory profile** for a user strictly from these propositions.

CRITICAL: You MUST respond with ONLY valid JSON. No explanations, no markdown, no extra text.

Propositions: {json.dumps(prop_data, indent=2, default=str)}

Instructions:
1. Normalize each proposition:
   - Extract Action/Behavior
   - Extract Context (academic, technical, career, leisure, media)
   - Extract Tools/Platforms mentioned
2. Cluster propositions by similarity into:
   - Workflows: repeated or structured processes
   - Preferences: favored methods, tools, or platforms  
   - Habits: behaviors done regularly or naturally
3. Merge highly similar propositions into a single cluster.
4. Abstract each cluster into 1–2 sentence declarative generalizations.
5. Output **JSON only** with this EXACT schema:

{{
  "user_id": "{user_id}",
  "long_term_generalizations": [
    {{
      "category": "workflow|preference|habit",
      "generalization": "<1–2 sentence summary>",
      "supporting_prop_ids": ["#id1", "#id2", "..."],
      "rationale": "<why these propositions support it>",
      "first_seen": "<earliest timestamp>",
      "last_seen": "<latest timestamp>",
      "tags": ["tooling","learning","career","productivity","media","research","other"]
    }}
  ]
}}

Constraints:
- Only use info from these propositions.
- Do not invent new actions, tools, or goals.
- Include all supporting proposition IDs with # prefix.
- Maintain accurate timestamps.
- Each generalization must be 1-2 sentences, under 500 characters.
- Rationale must explain the evidence, 20-1000 characters.
- Use only these tag options: tooling, learning, career, productivity, media, research, other.
- Category must be exactly: workflow, preference, or habit.

RESPOND WITH ONLY JSON. NO OTHER TEXT."""

    async def generate_long_term_memory(self, 
                                      user_id: str, 
                                      session: AsyncSession,
                                      force_generation: bool = False) -> Optional[List[LongTermMemory]]:
        """Generate long-term memories from recent propositions.
        
        Args:
            user_id: User identifier
            session: Database session
            force_generation: Skip proposition count check
            
        Returns:
            List of created LongTermMemory objects, or None if not enough propositions
        """
        try:
            # Fetch recent propositions
            propositions = await self.fetch_last_30_propositions(session)
            
            if len(propositions) < 5 and not force_generation:
                self.logger.info(f"Only {len(propositions)} propositions available, need at least 5")
                return None
                
            if len(propositions) == 0:
                self.logger.warning("No propositions available for memory generation")
                return None

            # Generate memories via AI
            memories_data = await self._call_ai_for_memories(user_id, propositions)
            
            # Create database records
            created_memories = []
            for memory_item in memories_data.long_term_generalizations:
                # Parse supporting proposition IDs (remove # prefix)
                supporting_ids = [int(prop_id.replace('#', '')) for prop_id in memory_item.supporting_prop_ids]
                
                # Validate proposition IDs exist
                valid_ids = [p.id for p in propositions if p.id in supporting_ids]
                if not valid_ids:
                    self.logger.warning(f"No valid proposition IDs found for memory: {memory_item.generalization[:50]}...")
                    continue
                
                memory = LongTermMemory(
                    category=memory_item.category,
                    generalization=memory_item.generalization,
                    supporting_prop_ids=json.dumps(valid_ids),
                    rationale=memory_item.rationale,
                    first_seen=datetime.fromisoformat(memory_item.first_seen.replace('Z', '+00:00')),
                    last_seen=datetime.fromisoformat(memory_item.last_seen.replace('Z', '+00:00')),
                    tags=json.dumps(memory_item.tags)
                )
                
                session.add(memory)
                created_memories.append(memory)
            
            await session.commit()
            self.logger.info(f"Created {len(created_memories)} long-term memories")
            return created_memories
            
        except Exception as e:
            await session.rollback()
            self.logger.error(f"Failed to generate long-term memories: {e}")
            raise

    async def _call_ai_for_memories(self, user_id: str, propositions: List[Proposition]) -> MemoryGenerationResponse:
        """Call AI to generate memories with strict JSON validation.
        
        Args:
            user_id: User identifier
            propositions: List of propositions to analyze
            
        Returns:
            Validated memory generation response
            
        Raises:
            ValueError: If AI response is invalid
        """
        prompt = self.build_memory_prompt(user_id, propositions)
        
        for attempt in range(self.config.max_retries):
            try:
                self.logger.debug(f"Calling OpenAI API for memory generation (attempt {attempt + 1})")
                
                response = await self.client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {
                            "role": "system", 
                            "content": "You are a precise data analyst. Respond with only valid JSON, no other text."
                        },
                        {
                            "role": "user", 
                            "content": prompt
                        }
                    ],
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    timeout=self.config.timeout_seconds
                )
                
                raw_content = response.choices[0].message.content.strip()
                
                # Clean up common JSON formatting issues
                raw_content = raw_content.replace('```json', '').replace('```', '').strip()
                
                # Parse JSON
                try:
                    json_data = json.loads(raw_content)
                except json.JSONDecodeError as e:
                    self.logger.warning(f"JSON parsing failed (attempt {attempt + 1}): {e}")
                    self.logger.debug(f"Raw response: {raw_content[:500]}...")
                    if attempt == self.config.max_retries - 1:
                        raise ValueError(f"AI returned invalid JSON after {self.config.max_retries} attempts: {e}")
                    continue
                
                # Validate with Pydantic
                try:
                    validated_response = MemoryGenerationResponse(**json_data)
                    self.logger.info(f"Successfully generated {len(validated_response.long_term_generalizations)} memory items")
                    return validated_response
                    
                except ValidationError as e:
                    self.logger.warning(f"Response validation failed (attempt {attempt + 1}): {e}")
                    self.logger.debug(f"Invalid data: {json_data}")
                    if attempt == self.config.max_retries - 1:
                        raise ValueError(f"AI response validation failed after {self.config.max_retries} attempts: {e}")
                    continue
                    
            except Exception as e:
                self.logger.error(f"API call failed (attempt {attempt + 1}): {e}")
                if attempt == self.config.max_retries - 1:
                    raise
                
        raise ValueError("Max retries exceeded for memory generation")

    async def get_memories_by_category(self, 
                                     session: AsyncSession, 
                                     category: Optional[str] = None,
                                     limit: int = 50) -> List[LongTermMemory]:
        """Fetch memories with optional category filtering.
        
        Args:
            session: Database session
            category: Optional category filter (workflow/preference/habit)
            limit: Maximum number of memories to return
            
        Returns:
            List of LongTermMemory objects
        """
        try:
            query = select(LongTermMemory).order_by(desc(LongTermMemory.created_at)).limit(limit)
            
            if category:
                query = query.where(LongTermMemory.category == category)
            
            result = await session.execute(query)
            memories = result.scalars().all()
            
            self.logger.debug(f"Retrieved {len(memories)} memories (category: {category})")
            return list(memories)
            
        except Exception as e:
            self.logger.error(f"Failed to fetch memories: {e}")
            raise
