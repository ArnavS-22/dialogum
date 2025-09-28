#!/usr/bin/env python3
"""
FastAPI server for GUM dashboard
Connects to GUM SQLite database and provides API endpoints
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Add the parent directory to Python path to import GUM modules
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import aiosqlite
from sqlalchemy import create_engine, text, select, func
from sqlalchemy.orm import sessionmaker

# Import GUM models
from gum.models import Proposition, Observation, LongTermMemory, init_db

app = FastAPI(title="GUM Dashboard API")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files not needed for API-only server

class PropositionResponse(BaseModel):
    id: int
    text: str
    reasoning: str
    confidence: Optional[int]
    decay: Optional[int]
    created_at: str
    updated_at: str
    revision_group: str
    version: int
    observation_count: int
    mixed_initiative_score: Optional[Dict[str, Any]] = None

class PropositionsListResponse(BaseModel):
    propositions: List[PropositionResponse]
    total_count: int


class MemoryResponse(BaseModel):
    id: int
    category: str
    generalization: str
    supporting_prop_ids: List[int]
    rationale: str
    first_seen: str
    last_seen: str
    tags: List[str]
    created_at: str
    updated_at: str
    

class MemoriesListResponse(BaseModel):
    memories: List[MemoryResponse]
    total_count: int

# Database connection
db_path = os.path.expanduser("~/.cache/gum/gum.db")
engine = None
Session = None

async def init_database():
    """Initialize database connection"""
    global engine, Session
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        print("Please run GUM first to create the database")
        return False
    
    try:
        engine, Session = await init_db(db_path)
        print(f"Connected to database: {db_path}")
        return True
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        return False

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    await init_database()

@app.get("/api/propositions", response_model=PropositionsListResponse)
async def get_propositions(
    limit: int = 50,
    offset: int = 0,
    confidence_min: Optional[int] = None
):
    """Get propositions from GUM database"""
    if not Session:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    try:
        async with Session() as session:
            # Build query
            query = select(Proposition)
            
            if confidence_min is not None:
                query = query.where(Proposition.confidence >= confidence_min)
            
            # Get total count
            count_query = select(func.count(Proposition.id))
            if confidence_min is not None:
                count_query = count_query.where(Proposition.confidence >= confidence_min)
            total_count_result = await session.execute(count_query)
            total_count = total_count_result.scalar()
            
            # Get propositions with pagination
            propositions_result = await session.execute(
                query.order_by(Proposition.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            
            # Convert to response format
            proposition_responses = []
            for prop in propositions_result.scalars():
                # Calculate mixed-initiative score (mock for now)
                mixed_initiative_score = calculate_mixed_initiative_score(prop)
                
                proposition_responses.append(PropositionResponse(
                    id=prop.id,
                    text=prop.text,
                    reasoning=prop.reasoning,
                    confidence=prop.confidence,
                    decay=prop.decay,
                    created_at=prop.created_at.isoformat() if prop.created_at else "",
                    updated_at=prop.updated_at.isoformat() if prop.updated_at else "",
                    revision_group=prop.revision_group,
                    version=prop.version,
                    observation_count=len(prop.observations) if prop.observations else 0,
                    mixed_initiative_score=mixed_initiative_score
                ))
            
            return PropositionsListResponse(
                propositions=proposition_responses,
                total_count=total_count
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

def calculate_mixed_initiative_score(proposition: Proposition) -> Dict[str, Any]:
    """Calculate mixed-initiative score for a proposition"""
    # Mock calculation - in real implementation, this would use the decision engine
    
    confidence = proposition.confidence or 5
    confidence_normalized = confidence / 10.0
    
    # Mock attention level (would come from attention monitor)
    attention_level = 0.07  # Mock low attention
    
    # Mock decision calculation
    if confidence_normalized > 0.8:
        decision = "autonomous_action"
        expected_utility = 0.8 + (attention_level * 0.2)
    elif confidence_normalized > 0.5:
        decision = "dialogue"
        expected_utility = 0.5 + (attention_level * 0.3)
    else:
        decision = "no_action"
        expected_utility = 0.2
    
    return {
        "decision": decision,
        "expected_utility": round(expected_utility, 3),
        "confidence_normalized": round(confidence_normalized, 3),
        "attention_level": attention_level,
        "interruption_cost": round(-attention_level * 2, 3)
    }

@app.get("/api/propositions/{proposition_id}")
async def get_proposition(proposition_id: int):
    """Get a specific proposition by ID"""
    if not Session:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    try:
        async with Session() as session:
            proposition = await session.get(Proposition, proposition_id)
            if not proposition:
                raise HTTPException(status_code=404, detail="Proposition not found")
            
            mixed_initiative_score = calculate_mixed_initiative_score(proposition)
            
            return PropositionResponse(
                id=proposition.id,
                text=proposition.text,
                reasoning=proposition.reasoning,
                confidence=proposition.confidence,
                decay=proposition.decay,
                created_at=proposition.created_at.isoformat() if proposition.created_at else "",
                updated_at=proposition.updated_at.isoformat() if proposition.updated_at else "",
                revision_group=proposition.revision_group,
                version=proposition.version,
                observation_count=len(proposition.observations) if proposition.observations else 0,
                mixed_initiative_score=mixed_initiative_score
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/memories", response_model=MemoriesListResponse)
async def get_memories(
    limit: int = 50,
    offset: int = 0,
    category: Optional[str] = None
):
    """Get long-term memories from GUM database"""
    if not Session:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    # Validate category parameter
    valid_categories = ["workflow", "preference", "habit"]
    if category and category not in valid_categories:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}"
        )
    
    try:
        async with Session() as session:
            # Build query
            query = select(LongTermMemory)
            
            if category:
                query = query.where(LongTermMemory.category == category)
            
            # Get total count
            count_query = select(func.count(LongTermMemory.id))
            if category:
                count_query = count_query.where(LongTermMemory.category == category)
            total_count_result = await session.execute(count_query)
            total_count = total_count_result.scalar()
            
            # Get memories with pagination
            memories_result = await session.execute(
                query.order_by(LongTermMemory.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            
            # Convert to response format
            memory_responses = []
            for memory in memories_result.scalars():
                memory_responses.append(MemoryResponse(
                    id=memory.id,
                    category=memory.category,
                    generalization=memory.generalization,
                    supporting_prop_ids=memory.supporting_proposition_ids,  # Uses property
                    rationale=memory.rationale,
                    first_seen=memory.first_seen.isoformat() if memory.first_seen else "",
                    last_seen=memory.last_seen.isoformat() if memory.last_seen else "",
                    tags=memory.tag_list,  # Uses property
                    created_at=memory.created_at.isoformat() if memory.created_at else "",
                    updated_at=memory.updated_at.isoformat() if memory.updated_at else ""
                ))
            
            return MemoriesListResponse(
                memories=memory_responses,
                total_count=total_count
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/memories/{memory_id}")
async def get_memory(memory_id: int):
    """Get a specific memory by ID"""
    if not Session:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    try:
        async with Session() as session:
            memory = await session.get(LongTermMemory, memory_id)
            if not memory:
                raise HTTPException(status_code=404, detail="Memory not found")
            
            return MemoryResponse(
                id=memory.id,
                category=memory.category,
                generalization=memory.generalization,
                supporting_prop_ids=memory.supporting_proposition_ids,
                rationale=memory.rationale,
                first_seen=memory.first_seen.isoformat() if memory.first_seen else "",
                last_seen=memory.last_seen.isoformat() if memory.last_seen else "",
                tags=memory.tag_list,
                created_at=memory.created_at.isoformat() if memory.created_at else "",
                updated_at=memory.updated_at.isoformat() if memory.updated_at else ""
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.post("/api/memories/generate")
async def generate_memory_manually():
    """Manually trigger memory generation for testing purposes"""
    if not Session:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    try:
        # Import here to avoid circular imports
        from gum.gum import gum
        from gum.memory_service import LongTermMemoryService, MemoryServiceConfig
        from openai import AsyncOpenAI
        import os
        
        # Create temporary gum instance for manual memory generation
        client = AsyncOpenAI(
            api_key=os.getenv("GUM_LM_API_KEY") or os.getenv("OPENAI_API_KEY") or "None"
        )
        
        memory_config = MemoryServiceConfig(model="gpt-4", temperature=0.1)
        memory_service = LongTermMemoryService(
            openai_client=client,
            config=memory_config
        )
        
        async with Session() as session:
            memories = await memory_service.generate_long_term_memory(
                user_id="manual_trigger",
                session=session,
                force_generation=True
            )
            
            if memories:
                return {
                    "status": "success",
                    "message": f"Generated {len(memories)} memories",
                    "memories": [
                        {
                            "id": mem.id,
                            "category": mem.category,
                            "generalization": mem.generalization[:100] + "..." if len(mem.generalization) > 100 else mem.generalization
                        } for mem in memories
                    ]
                }
            else:
                return {
                    "status": "no_memories",
                    "message": "No memories were generated (insufficient propositions or other constraints)"
                }
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Memory generation failed: {str(e)}")


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database_connected": Session is not None,
        "database_path": db_path,
        "database_exists": os.path.exists(db_path)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
