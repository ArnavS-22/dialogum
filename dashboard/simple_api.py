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

# Database path
# Allow override for testing and deployment
db_path = os.getenv("GUM_DB_PATH", os.path.expanduser("~/.cache/gum/gum.db"))

# ──────────────────────────────────────────────────────────────────────────────
# Mixed-initiative engine integration (real engine, attention monitor)
# ──────────────────────────────────────────────────────────────────────────────
try:
    # Import real engine and attention monitor from GUM
    from gum.decision import MixedInitiativeDecisionEngine, DecisionContext
    from gum.attention import AttentionMonitor
    from gum.models import Proposition

    _ENGINE: MixedInitiativeDecisionEngine | None = None
    _ATTN: AttentionMonitor | None = None

    @app.on_event("startup")
    async def _startup_init_engine():
        # Initialize decision engine and start attention monitoring in background
        # Fail gracefully if environment is missing dependencies (e.g., non‑macOS)
        global _ENGINE, _ATTN
        try:
            _ENGINE = MixedInitiativeDecisionEngine(debug=False)
            _ATTN = AttentionMonitor(debug=False)
            _ATTN.start_monitoring()
        except Exception:
            _ENGINE = None
            _ATTN = None

    @app.on_event("shutdown")
    async def _shutdown_stop_engine():
        global _ATTN
        try:
            if _ATTN:
                _ATTN.stop_monitoring()
        except Exception:
            pass
except Exception:
    # If imports fail, leave uninitialized. Downstream calls will error (no fallback).
    _ENGINE = None
    _ATTN = None

def calculate_mixed_initiative_score(proposition_data: dict) -> Dict[str, Any]:
    """Calculate mixed-initiative score for a proposition using the real engine only.

    No fallback. If the engine or attention monitor are unavailable, raise 500.
    """
    try:
        if _ENGINE is None or _ATTN is None:
            raise HTTPException(status_code=500, detail="Mixed-initiative engine/attention not initialized")

        # Get current attention state
        attn = _ATTN.get_current_attention()

        # Build a lightweight Proposition object for decision context
        prop = Proposition(
            text=proposition_data.get('text', '') or '',
            reasoning=proposition_data.get('reasoning', '') or '',
            confidence=proposition_data.get('confidence', 5) or 5,
        )

        decision, metadata = _ENGINE.make_decision(DecisionContext(
            proposition=prop,
            user_attention_level=attn.focus_level,
            active_application=attn.active_application,
            idle_time_seconds=attn.idle_time_seconds,
        ))

        # Extract expected utility for chosen action
        eus = metadata.get("expected_utilities", {})
        eu_for_choice = eus.get(decision)
        utilities_used = metadata.get("utilities_used", {})

        # Approximate an interruption cost signal from dialogue false-utility
        interruption_cost = -utilities_used.get("u_dialogue_goal_false", 0.0)

        return {
            "decision": decision,
            "expected_utility": round(eu_for_choice, 3) if eu_for_choice is not None else None,
            "confidence_normalized": round((metadata.get("confidence", 5) / 10.0), 3),
            "attention_level": round(metadata.get("attention_level", attn.focus_level), 3),
            "interruption_cost": round(interruption_cost, 3),
        }

    except HTTPException:
        raise
    except Exception as e:
        # Explicit failure — caller gets 500; we do not fabricate decisions
        raise HTTPException(status_code=500, detail=f"Decision engine error: {e}")

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
