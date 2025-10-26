# Clarification Detection Engine - Setup and Usage Guide

## Overview

The Clarification Detection Engine is a middle-layer system that analyzes GUM propositions against 12 research-grounded psychological factors to determine if they should be flagged for clarifying dialogue through Gates.

This system uses a comprehensive LLM-based approach with post-processing validation to ensure accurate detection of when propositions trigger human clarification needs.

## The 12 Psychological Factors

Each proposition is analyzed against these factors:

1. **Identity Mismatch** - Trait claims that could conflict with self-concept
2. **Over-Specific Behavioral Claim (Surveillance)** - Hyper-granular details that feel invasive
3. **Inferred Motives** - Claims about WHY someone did something
4. **Negative Evaluation / Face Threat** - Socially critical or disapproving statements
5. **Over-Positive Claims** - Unexpected praise that contradicts self-view
6. **Lack of Evidence / Opaque Reasoning** - Confident claims without justification
7. **Over-Generalization** - Absolutist language ("always", "never", etc.)
8. **Sensitive Domain** - Topics touching private life (health, finance, relationships)
9. **Actor-Observer Mismatch** - Trait attribution without situational context
10. **Public Exposure / Reputation Risk** - Claims that could affect social image
11. **Interpretive Ambiguity** - Vague terms with multiple meanings
12. **Tone / Certainty Imbalance** - Language assertiveness mismatched with evidence

## System Architecture

```
New Proposition Created (GUM)
    ↓
ClarificationDetector.analyze()
    ↓
1. Build Context (prop + reasoning + observations)
    ↓
2. Call LLM (comprehensive prompt analyzing all 12 factors)
    ↓
3. Validate Response (verify evidence citations, check consistency)
    ↓
4. Persist ClarificationAnalysis to Database
    ↓
5. If flagged + not shadow_mode → Route to Gates
```

### Key Components

- **`gum/clarification_models.py`** - Database schema for storing analysis results
- **`gum/clarification/prompts.py`** - Comprehensive LLM prompt (analyzes all 12 factors)
- **`gum/clarification/detector.py`** - Main detection logic and validation
- **`gum/config.py`** - Configuration (model, thresholds, shadow mode)
- **`gum/gum.py`** - Integration into proposition processing flow
- **`dashboard/api_server.py`** - API endpoints for querying analyses

## Setup Instructions

### 1. Run Database Migration

Create the `clarification_analyses` table:

```bash
python -m gum.migrate_clarification
```

This will create the table at `~/.cache/gum/gum.db`.

### 2. Configure the System

Edit your GUM configuration or set environment variables:

**In Code:**
```python
from gum.config import GumConfig

config = GumConfig()

# Enable clarification detection
config.clarification.enabled = True

# Start in shadow mode (collect data, don't route to Gates)
config.clarification.shadow_mode = True

# Set the threshold (0.0-1.0) for flagging
config.clarification.threshold = 0.6

# Set the LLM model
config.clarification.model = "gpt-4-turbo"

# Set temperature for consistency
config.clarification.temperature = 0.1
```

**Via Environment Variables:**
```bash
export CLARIFICATION_ENABLED=true
export CLARIFICATION_SHADOW_MODE=true
export CLARIFICATION_MODEL=gpt-4-turbo
```

### 3. Run GUM with Clarification Detection

The detector runs automatically when new propositions are created:

```python
from gum import gum

# Create GUM instance (detector runs automatically)
g = gum(
    user_name="Arnav",
    model="gpt-4",
    config=config,
    # ... other parameters
)

# Start observing - clarification detection happens automatically
await g.start()
```

## Usage

### Automatic Detection

Once enabled, the detector runs automatically on every new proposition:

1. GUM creates a new proposition
2. Detector analyzes it against all 12 factors
3. Results are persisted to `clarification_analyses` table
4. If flagged and not in shadow mode, routes to Gates

### API Endpoints

The API server exposes three endpoints:

#### 1. Get Clarification Analysis for a Proposition

```bash
GET /api/propositions/{proposition_id}/clarification
```

**Response:**
```json
{
  "has_analysis": true,
  "needs_clarification": true,
  "clarification_score": 0.78,
  "triggered_factors": ["identity_mismatch", "opacity"],
  "reasoning": "Top concern: trait attribution without evidence.",
  "factor_scores": {
    "identity_mismatch": 0.85,
    "surveillance": 0.0,
    "inferred_intent": 0.0,
    ...
  },
  "created_at": "2025-10-26T12:34:56"
}
```

#### 2. Get All Flagged Propositions

```bash
GET /api/propositions/flagged?limit=50
```

**Response:**
```json
[
  {
    "proposition": {
      "id": 123,
      "text": "Arnav is careless with code organization.",
      "reasoning": "...",
      ...
    },
    "clarification_score": 0.85,
    "triggered_factors": ["identity_mismatch", "face_threat"],
    "reasoning": "Trait claim with negative evaluation"
  },
  ...
]
```

#### 3. Regular Propositions Endpoint (unchanged)

```bash
GET /api/propositions?limit=50&offset=0
```

### Querying Analyses Directly

You can also query the database directly:

```python
from gum.models import init_db
from gum.clarification_models import ClarificationAnalysis
from sqlalchemy import select

# Initialize database
engine, Session = await init_db(...)

async with Session() as session:
    # Get all flagged propositions
    result = await session.execute(
        select(ClarificationAnalysis)
        .where(ClarificationAnalysis.needs_clarification == True)
        .order_by(ClarificationAnalysis.clarification_score.desc())
    )
    
    for analysis in result.scalars():
        print(f"Proposition {analysis.proposition_id}")
        print(f"Score: {analysis.clarification_score}")
        print(f"Triggered: {analysis.triggered_factors}")
        print(f"Reasoning: {analysis.reasoning_log}")
        print()
```

## Understanding the Results

### Clarification Score

- **0.0-0.3:** Low - unlikely to need clarification
- **0.3-0.6:** Medium - might need clarification depending on threshold
- **0.6-0.8:** High - likely needs clarification
- **0.8-1.0:** Very High - definitely needs clarification

### Triggered Factors

A factor is "triggered" when its score >= 0.6. The triggered factors list shows which psychological drivers are present.

### Factor Scores

Each of the 12 factors has an individual score (0.0-1.0):
- **0.0:** Factor not present
- **0.3-0.5:** Factor mildly present
- **0.6-0.8:** Factor clearly present (triggered)
- **0.9-1.0:** Factor strongly present

### Reasoning Log

Natural language explanation of why the proposition was flagged, including:
- Top contributing factors
- Evidence from observations
- Specific concerns identified

## Shadow Mode vs. Active Mode

### Shadow Mode (Recommended Initially)

```python
config.clarification.shadow_mode = True
```

- Runs analysis on all propositions
- Persists results to database
- DOES NOT route to Gates
- Use this to collect data and validate accuracy

### Active Mode

```python
config.clarification.shadow_mode = False
```

- Runs analysis on all propositions
- Persists results to database
- Routes flagged propositions to Gates for clarification dialogue
- Only enable after validating accuracy in shadow mode

## Monitoring and Tuning

### Key Metrics to Track

1. **Triggered Rate:** % of propositions flagged for clarification
2. **Factor Distribution:** Which factors trigger most often
3. **Evidence Quality:** % of analyses with valid evidence citations
4. **Validation Pass Rate:** % of analyses that pass consistency checks

### Tuning the Threshold

The default threshold is 0.6. Adjust based on:

- **Too many false positives?** Increase threshold to 0.7 or 0.8
- **Missing important cases?** Decrease threshold to 0.5
- **Want high precision?** Use 0.7+
- **Want high recall?** Use 0.5-0.6

```python
config.clarification.threshold = 0.7  # More conservative
```

### Reviewing Logs

The detector logs detailed information:

```
INFO: Running clarification detection on 3 propositions...
INFO: Proposition 123 flagged for clarification (score=0.85)
DEBUG: Proposition 124 does not need clarification (score=0.32)
ERROR: Error analyzing proposition 125: ...
```

## Cost Estimation

Using GPT-4-turbo:
- ~$0.03 per proposition analyzed
- 789 existing propositions = ~$24 one-time
- Ongoing: ~$0.03 per new proposition
- Monthly (100 new props) = ~$3

## Troubleshooting

### "Database not connected"

Make sure you ran the migration:
```bash
python -m gum.migrate_clarification
```

### "ClarificationAnalysis not found"

Check that the import is correct:
```python
from gum.clarification_models import ClarificationAnalysis
```

### "Detector not running"

Verify configuration:
```python
# Check if enabled
print(config.clarification.enabled)  # Should be True

# Check GUM logs for detection messages
# Look for "Running clarification detection on X propositions..."
```

### High API Costs

If costs are too high:
1. Use `gpt-3.5-turbo` instead (lower quality but cheaper)
2. Add sampling - only analyze X% of propositions
3. Implement caching to avoid re-analyzing

## Next Steps

1. **Run Migration:** Create the database table
2. **Enable in Shadow Mode:** Start collecting data
3. **Analyze First 50 Props:** Review results for accuracy
4. **Tune Threshold:** Adjust based on false positive/negative rate
5. **Enable Active Mode:** Route to Gates when ready
6. **Monitor Metrics:** Track performance over time

## Technical Details

### Database Schema

The `clarification_analyses` table stores:
- One analysis per proposition (unique on `proposition_id`)
- Overall decision (`needs_clarification`) and score
- Individual scores for all 12 factors
- Full LLM response for debugging
- Evidence citations and reasoning
- Validation status and metadata

### Validation Layer

The detector validates LLM outputs:
1. Checks all 12 factors are present
2. Verifies evidence spans exist in observations
3. Validates observation IDs are real
4. Checks consistency (e.g., Factor 7 requires absolutist words)
5. Downgrades scores when evidence is missing

### Prompt Engineering

The comprehensive prompt includes:
- Detailed detection instructions for each factor
- Scoring rubrics (what 0.0, 0.6, 1.0 mean)
- Few-shot examples (coming soon)
- Strict JSON schema enforcement
- Evidence citation requirements

## Support

For issues or questions:
1. Check the logs in GUM output
2. Query the database to inspect analyses
3. Review the validation issues in `llm_raw_output`
4. Test with known propositions to verify behavior

## Future Enhancements

- [ ] Gates integration for clarification dialogues
- [ ] Dashboard UI for visualizing analyses
- [ ] Batch analysis script for existing propositions
- [ ] A/B testing framework for threshold tuning
- [ ] Human feedback loop for continuous improvement
- [ ] Factor-specific prompt templates
- [ ] Multi-model ensemble for higher accuracy

