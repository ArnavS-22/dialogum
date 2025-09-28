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
    mixed_initiative_score: Optional[Dict[str, Any]] = None

class PropositionsListResponse(BaseModel):
    propositions: List[PropositionResponse]
    total_count: int

# ─────────────────────────── Memories API models
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

# Database path
db_path = os.path.expanduser("~/.cache/gum/gum.db")

async def _ensure_long_term_memories_table(db: aiosqlite.Connection) -> None:
    """Create the long_term_memories table if it doesn't exist (idempotent)."""
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS long_term_memories (
            id INTEGER PRIMARY KEY,
            category TEXT NOT NULL,
            generalization TEXT NOT NULL,
            supporting_prop_ids TEXT NOT NULL,
            rationale TEXT NOT NULL,
            first_seen TEXT,
            last_seen TEXT,
            tags TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # Lightweight indexes for filtering/sorting
    await db.execute("CREATE INDEX IF NOT EXISTS idx_ltm_category ON long_term_memories(category)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_ltm_created_at ON long_term_memories(created_at)")
    await db.commit()

def calculate_mixed_initiative_score(proposition_data: dict) -> Dict[str, Any]:
    """Calculate mixed-initiative score for a proposition"""
    confidence = proposition_data.get('confidence', 5)
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
                
                # Calculate mixed-initiative score
                mixed_initiative_score = calculate_mixed_initiative_score(prop_data)
                
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
                    mixed_initiative_score=mixed_initiative_score
                ))
            
            return PropositionsListResponse(
                propositions=proposition_responses,
                total_count=total_count
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# ─────────────────────────── Memories API
@app.get("/api/memories", response_model=MemoriesListResponse)
async def get_memories(
    limit: int = 50,
    offset: int = 0,
    category: Optional[str] = None
):
    if not os.path.exists(db_path):
        raise HTTPException(status_code=500, detail="GUM database not found. Please run GUM first.")

    valid_categories = {"workflow", "preference", "habit"}
    if category and category not in valid_categories:
        raise HTTPException(status_code=400, detail="Invalid category. Use workflow|preference|habit")

    try:
        async with aiosqlite.connect(db_path) as db:
            await _ensure_long_term_memories_table(db)
            where_clause = ""
            params: List[Any] = []
            if category:
                where_clause = "WHERE category = ?"
                params.append(category)

            # Count
            count_q = f"SELECT COUNT(*) FROM long_term_memories {where_clause}"
            async with db.execute(count_q, params) as cur:
                total_count = (await cur.fetchone())[0]

            # Fetch
            q = f"""
                SELECT id, category, generalization, supporting_prop_ids, rationale,
                       first_seen, last_seen, tags, created_at, updated_at
                FROM long_term_memories
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            query_params = params + [limit, offset]
            async with db.execute(q, query_params) as cur:
                rows = await cur.fetchall()

            def parse_json_array(s: Optional[str]) -> List[Any]:
                try:
                    return json.loads(s) if s else []
                except Exception:
                    return []

            memories: List[MemoryResponse] = []
            for r in rows:
                memories.append(MemoryResponse(
                    id=r[0],
                    category=r[1],
                    generalization=r[2],
                    supporting_prop_ids=[int(x) for x in parse_json_array(r[3]) if isinstance(x, (int, str)) and str(x).isdigit()],
                    rationale=r[4],
                    first_seen=str(r[5]) if r[5] is not None else "",
                    last_seen=str(r[6]) if r[6] is not None else "",
                    tags=[str(x) for x in parse_json_array(r[7])],
                    created_at=str(r[8]) if r[8] is not None else "",
                    updated_at=str(r[9]) if r[9] is not None else ""
                ))

            return MemoriesListResponse(memories=memories, total_count=total_count)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/memories/{memory_id}", response_model=MemoryResponse)
async def get_memory(memory_id: int):
    if not os.path.exists(db_path):
        raise HTTPException(status_code=500, detail="GUM database not found. Please run GUM first.")

    try:
        async with aiosqlite.connect(db_path) as db:
            await _ensure_long_term_memories_table(db)
            q = (
                "SELECT id, category, generalization, supporting_prop_ids, rationale, "
                "first_seen, last_seen, tags, created_at, updated_at "
                "FROM long_term_memories WHERE id = ?"
            )
            async with db.execute(q, (memory_id,)) as cur:
                row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Memory not found")

            def parse_json_array(s: Optional[str]) -> List[Any]:
                try:
                    return json.loads(s) if s else []
                except Exception:
                    return []

            return MemoryResponse(
                id=row[0],
                category=row[1],
                generalization=row[2],
                supporting_prop_ids=[int(x) for x in parse_json_array(row[3]) if isinstance(x, (int, str)) and str(x).isdigit()],
                rationale=row[4],
                first_seen=str(row[5]) if row[5] is not None else "",
                last_seen=str(row[6]) if row[6] is not None else "",
                tags=[str(x) for x in parse_json_array(row[7])],
                created_at=str(row[8]) if row[8] is not None else "",
                updated_at=str(row[9]) if row[9] is not None else "",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/memories/{memory_id}/propositions")
async def get_memory_propositions(memory_id: int):
    """Get the supporting propositions for a specific memory."""
    if not os.path.exists(db_path):
        raise HTTPException(status_code=500, detail="GUM database not found. Please run GUM first.")

    try:
        async with aiosqlite.connect(db_path) as db:
            # First, get the memory to verify it exists and get supporting prop IDs
            memory_query = "SELECT supporting_prop_ids FROM long_term_memories WHERE id = ?"
            async with db.execute(memory_query, (memory_id,)) as cur:
                memory_row = await cur.fetchone()
            
            if not memory_row:
                raise HTTPException(status_code=404, detail="Memory not found")
            
            # Parse the supporting proposition IDs
            supporting_prop_ids = json.loads(memory_row[0]) if memory_row[0] else []
            if not supporting_prop_ids:
                return {"propositions": []}
            
            # Convert to integers and create placeholders for the query
            prop_ids = [int(pid) for pid in supporting_prop_ids if str(pid).isdigit()]
            if not prop_ids:
                return {"propositions": []}
            
            # Fetch the actual propositions
            placeholders = ",".join("?" * len(prop_ids))
            propositions_query = f"""
                SELECT id, text, reasoning, confidence, decay, created_at, updated_at, 
                       revision_group, version
                FROM propositions 
                WHERE id IN ({placeholders})
                ORDER BY created_at DESC
            """
            
            async with db.execute(propositions_query, prop_ids) as cur:
                rows = await cur.fetchall()
            
            propositions = []
            for row in rows:
                propositions.append(PropositionResponse(
                    id=row[0],
                    text=row[1],
                    reasoning=row[2],
                    confidence=row[3],
                    decay=row[4],
                    created_at=row[5],
                    updated_at=row[6],
                    revision_group=row[7],
                    version=row[8],
                    observation_count=0,  # Not available in current schema
                    mixed_initiative_score=None  # Not available in current schema
                ))
            
            return {"propositions": propositions}
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.post("/api/memories/generate")
async def generate_memory_manually():
    """Manually trigger memory generation using the service and ORM session."""
    try:
        # Lazy imports to avoid heavier startup
        from openai import AsyncOpenAI
        from gum.memory_service import LongTermMemoryService, MemoryServiceConfig
        from gum.models import init_db

        client = AsyncOpenAI(
            api_key=os.getenv("GUM_LM_API_KEY") or os.getenv("OPENAI_API_KEY") or "None"
        )
        memory_service = LongTermMemoryService(
            openai_client=client,
            config=MemoryServiceConfig(model=os.getenv("GUM_LM_MODEL", "gpt-4"), temperature=0.1)
        )

        # Create ORM session and run generation
        engine, Session = await init_db()
        async with Session() as session:
            memories = await memory_service.generate_long_term_memory(
                user_id="manual_trigger",
                session=session,
                force_generation=True
            )

        return {
            "status": "success",
            "generated": len(memories or []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")

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
