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
from gum.models import Proposition, Observation, init_db
from gum.ambiguity_models import AmbiguityAnalysis, UrgencyAssessment

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
    # Ambiguity
    entropy_score: Optional[float] = None
    is_ambiguous: Optional[bool] = None
    # Urgency
    urgency_level: Optional[str] = None
    urgency_score: Optional[float] = None
    time_sensitive: Optional[bool] = None
    should_clarify_by: Optional[str] = None

class PropositionsListResponse(BaseModel):
    propositions: List[PropositionResponse]
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
                # Load latest ambiguity analysis (if any)
                ambiguity_score = None
                ambiguity_flag = None
                try:
                    aa_q = (
                        select(AmbiguityAnalysis)
                        .where(AmbiguityAnalysis.proposition_id == prop.id)
                        .order_by(AmbiguityAnalysis.id.desc())
                        .limit(1)
                    )
                    aa_res = await session.execute(aa_q)
                    aa = aa_res.scalars().first()
                    if aa:
                        ambiguity_score = aa.entropy_score
                        ambiguity_flag = aa.is_ambiguous
                except Exception:
                    ambiguity_score = None
                    ambiguity_flag = None

                # Load urgency assessment (if any)
                urgency_level = None
                urgency_score = None
                time_sensitive = None
                should_clarify_by = None
                try:
                    ua_q = select(UrgencyAssessment).where(UrgencyAssessment.proposition_id == prop.id).limit(1)
                    ua_res = await session.execute(ua_q)
                    ua = ua_res.scalars().first()
                    if ua:
                        urgency_level = ua.urgency_level
                        urgency_score = ua.urgency_score
                        time_sensitive = ua.time_sensitive
                        should_clarify_by = ua.should_clarify_by.isoformat() if ua.should_clarify_by else None
                except Exception:
                    pass
                
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
                    entropy_score=ambiguity_score,
                    is_ambiguous=ambiguity_flag,
                    urgency_level=urgency_level,
                    urgency_score=urgency_score,
                    time_sensitive=time_sensitive,
                    should_clarify_by=should_clarify_by,
                ))
            
            return PropositionsListResponse(
                propositions=proposition_responses,
                total_count=total_count
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

def _noop():
    return None

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

            # Load ambiguity/urgency for single proposition
            ambiguity_score = None
            ambiguity_flag = None
            aa_q = (
                select(AmbiguityAnalysis)
                .where(AmbiguityAnalysis.proposition_id == proposition.id)
                .order_by(AmbiguityAnalysis.id.desc())
                .limit(1)
            )
            aa_res = await session.execute(aa_q)
            aa = aa_res.scalars().first()
            if aa:
                ambiguity_score = aa.entropy_score
                ambiguity_flag = aa.is_ambiguous

            urgency_level = None
            urgency_score = None
            time_sensitive = None
            should_clarify_by = None
            ua_q = select(UrgencyAssessment).where(UrgencyAssessment.proposition_id == proposition.id).limit(1)
            ua_res = await session.execute(ua_q)
            ua = ua_res.scalars().first()
            if ua:
                urgency_level = ua.urgency_level
                urgency_score = ua.urgency_score
                time_sensitive = ua.time_sensitive
                should_clarify_by = ua.should_clarify_by.isoformat() if ua.should_clarify_by else None

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
                entropy_score=ambiguity_score,
                is_ambiguous=ambiguity_flag,
                urgency_level=urgency_level,
                urgency_score=urgency_score,
                time_sensitive=time_sensitive,
                should_clarify_by=should_clarify_by,
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

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
