#!/usr/bin/env python3
"""
Simple FastAPI server for GUM dashboard
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
from pydantic import BaseModel
import aiosqlite

app = FastAPI(title="GUM Dashboard API")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

class PropositionsListResponse(BaseModel):
    propositions: List[PropositionResponse]
    total_count: int

# Database path
db_path = os.path.expanduser("~/.cache/gum/gum.db")

def _noop():
    return None

@app.get("/api/propositions", response_model=PropositionsListResponse)
async def get_propositions(
    limit: int = 50,
    offset: int = 0,
    confidence_min: Optional[int] = None
):
    """Get propositions from GUM database using raw SQLite"""
    if not os.path.exists(db_path):
        raise HTTPException(status_code=500, detail="GUM database not found. Please run GUM first.")
    
    try:
        async with aiosqlite.connect(db_path) as db:
            # Build query
            where_clause = ""
            params = []
            if confidence_min is not None:
                where_clause = "WHERE confidence >= ?"
                params.append(confidence_min)
            
            # Get total count
            count_query = f"SELECT COUNT(*) FROM propositions {where_clause}"
            async with db.execute(count_query, params) as cursor:
                total_count = (await cursor.fetchone())[0]
            
            # Get propositions with pagination
            query = f"""
                SELECT id, text, reasoning, confidence, decay, created_at, updated_at, 
                       revision_group, version
                FROM propositions 
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            query_params = params + [limit, offset]
            
            async with db.execute(query, query_params) as cursor:
                rows = await cursor.fetchall()
                
            # Convert to response format
            proposition_responses = []
            for row in rows:
                prop_data = {
                    'id': row[0],
                    'text': row[1],
                    'reasoning': row[2],
                    'confidence': row[3],
                    'decay': row[4],
                    'created_at': row[5],
                    'updated_at': row[6],
                    'revision_group': row[7],
                    'version': row[8]
                }
                
                # Get observation count
                obs_query = "SELECT COUNT(*) FROM observation_proposition WHERE proposition_id = ?"
                async with db.execute(obs_query, (row[0],)) as obs_cursor:
                    observation_count = (await obs_cursor.fetchone())[0]
                
                proposition_responses.append(PropositionResponse(
                    id=prop_data['id'],
                    text=prop_data['text'],
                    reasoning=prop_data['reasoning'],
                    confidence=prop_data['confidence'],
                    decay=prop_data['decay'],
                    created_at=prop_data['created_at'],
                    updated_at=prop_data['updated_at'],
                    revision_group=prop_data['revision_group'],
                    version=prop_data['version'],
                    observation_count=observation_count,
                ))
            
            return PropositionsListResponse(
                propositions=proposition_responses,
                total_count=total_count
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database_path": db_path,
        "database_exists": os.path.exists(db_path)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
