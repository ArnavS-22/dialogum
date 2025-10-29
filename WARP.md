# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

**GUM (General User Models)** is a system for learning about users by observing any interaction with their computer. It takes unstructured observations (e.g., device screenshots) and constructs confidence-weighted propositions that capture user knowledge and preferences. The system introduces an architecture that:

1. **Infers** new propositions from multimodal observations  
2. **Retrieves** related propositions for context  
3. **Continuously revises** existing propositions

The core novelty includes a mixed-initiative decision engine based on Horvitz's principles that determines when to intervene based on real-time user attention monitoring.

Official documentation: https://generalusermodels.github.io/gum/

## Common Commands

### Installation

```bash
# Install from PyPI
pip install -U gum-ai

# Install from source (editable)
pip install --editable .
```

### Running GUM

```bash
# Start GUM server (listens to user interactions)
# Requires OPENAI_API_KEY and USER_NAME env variables
gum

# Query existing propositions
gum -q

# Query with search term
gum -q "coding preferences" -l 10

# Reset cache
gum --reset-cache
```

### Environment Setup

Required environment variables:
- `USER_NAME`: Your full name
- `OPENAI_API_KEY`: OpenAI API key for GPT models
- `MODEL_NAME` (optional): Model to use (default: `gpt-4o-mini`)
- `GUM_LM_API_BASE` (optional): Custom API base URL for local LMs
- `GUM_LM_API_KEY` (optional): API key for custom LM endpoint

Optional batching configuration:
- `MIN_BATCH_SIZE`: Minimum observations to trigger batch processing (default: 5)
- `MAX_BATCH_SIZE`: Maximum observations per batch (default: 15)

### Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest test_end_to_end_real.py

# Run with verbose output
pytest -v test_real_functionality.py

# Run specific test function
pytest test_end_to_end_real.py::test_full_pipeline_simulation
```

### Documentation

```bash
# Serve documentation locally
mkdocs serve

# Build documentation
mkdocs build
```

### Dashboard (Next.js Frontend)

```bash
# Install dependencies
cd dashboard
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

## Architecture

### Core Components

**`gum/gum.py`** - Main orchestrator class  
The `gum` class manages the entire system lifecycle. Key responsibilities:
- Initializes and manages Observer instances
- Coordinates proposition generation, revision, and retrieval  
- Handles database connections and batch processing
- Orchestrates mixed-initiative decision making and attention monitoring
- Provides query interface for retrieving propositions

**`gum/models.py`** - SQLAlchemy ORM models  
Defines the database schema:
- `Observation`: Raw observations from observers (screen content, notifications, etc.)
- `Proposition`: Inferred statements about the user with confidence scores
- `observation_proposition`: Many-to-many relationship table
- Full-text search (FTS5) support for proposition retrieval

**`gum/schemas.py`** - Pydantic schemas  
Validates LLM outputs and API payloads:
- `PropositionSchema`: Structured proposition generation from LLM
- `RelationSchema`: Similarity relationships between propositions
- `AuditSchema`: Privacy audit results
- `Update`: Observer update payloads

### Observer System

**`gum/observers/observer.py`** - Base observer interface  
Abstract base class for all observers. Defines:
- Async queue-based update delivery
- Worker lifecycle management
- Exception handling and cleanup

**`gum/observers/screen.py`** - Screen capture observer  
Captures and analyzes screen content using:
- macOS Quartz framework for window geometry detection
- `mss` for multi-monitor screenshot capture
- `pynput` for mouse/keyboard event monitoring
- GPT-4 Vision for transcribing and summarizing screen content
- Smart debouncing to avoid redundant captures
- App visibility filtering (skip captures when certain apps are visible)

### Proposition Processing

**Batching (`gum/batcher.py`)**  
Reduces API costs by batching observations:
- Persistent queue backed by SQLite (`persist-queue`)
- Configurable min/max batch sizes
- FIFO processing with async event notification

**Prompts (`gum/prompts/`)**  
LLM prompts for different stages:
- `PROPOSE_PROMPT`: Generate propositions from observations
- `REVISE_PROMPT`: Update existing propositions with new evidence
- `SIMILAR_PROMPT`: Find related propositions
- `AUDIT_PROMPT`: Privacy/consent filtering

### Mixed-Initiative System

**`gum/decision.py`** - Decision engine  
Core novelty: attention-aware mixed-initiative decision making.

Implements Horvitz's expected utility framework to choose between:
1. **No action** - Accept proposition silently
2. **Dialogue** - Ask user for confirmation (GATE questions)
3. **Autonomous action** - Take action or show suggestion

Key mechanism: Dynamically adjusts interruption costs based on real-time user attention level. High focus → high interruption cost. Low focus → low interruption cost.

Uses configuration from `config.py`:
- Base utility values for each action/outcome combination
- Attention thresholds (high focus: 0.8, low focus: 0.3)
- Penalty multipliers for focus states

**`gum/attention.py`** - Attention monitor  
Monitors user attention in real-time using:
- Keyboard/mouse activity frequency via `pynput`
- Active application detection via macOS AppleScript
- Application classification (focus apps vs casual apps)
- App switching patterns
- Idle time calculation

Produces `AttentionState` with focus level from 0.0 (idle) to 1.0 (highly focused).

**`gum/config.py`** - Configuration dataclasses  
- `DecisionConfig`: Utility values and thresholds
- `AttentionConfig`: Monitoring parameters  
- `GumConfig`: Top-level config with environment variable loading

### Database Utilities

**`gum/db_utils.py`**  
Helper functions for database operations:
- `search_propositions_bm25()`: BM25 full-text search over propositions
- `get_related_observations()`: Fetch observations linked to propositions
- Async SQLAlchemy session management

### CLI

**`gum/cli.py`**  
Command-line interface entry point. Supports:
- Starting the GUM server with observer monitoring
- Querying propositions
- Resetting cache
- Configuring batch sizes and models

## Key Workflows

### Starting a GUM Instance

1. Set required environment variables (`USER_NAME`, `OPENAI_API_KEY`)
2. Grant Terminal accessibility and screen recording permissions in macOS
3. Run `gum` to start observer loop
4. GUM captures screen observations, generates propositions, and stores in SQLite DB
5. Query propositions with `gum -q`

### Adding a New Observer

1. Subclass `Observer` in `gum/observers/`
2. Implement `_worker()` method with observation logic
3. Push updates to `self.update_queue` with `Update` schema
4. Instantiate observer when creating `gum()` instance
5. Observer lifecycle managed automatically by `gum` class

### Proposition Lifecycle

1. **Observation** - Observer captures raw data (screenshot, notification, etc.)
2. **Batching** - Observations queued in `ObservationBatcher` until batch size reached
3. **Inference** - LLM generates propositions from batch using `PROPOSE_PROMPT`
4. **Similarity** - New propositions compared to existing ones via `SIMILAR_PROMPT`
5. **Revision** - Similar propositions merged/updated using `REVISE_PROMPT`
6. **Storage** - Propositions stored in SQLite with FTS5 indexing
7. **Decision** (if mixed-initiative enabled) - Decision engine determines intervention strategy

### Mixed-Initiative Flow

1. New proposition generated with confidence score (1-10)
2. `AttentionMonitor` provides current focus level
3. `MixedInitiativeDecisionEngine` adjusts utilities based on attention
4. Calculate expected utilities for: no_action, dialogue, autonomous_action
5. Select action with highest expected utility
6. Execute decision (store metadata for logging/debugging)

## Important Patterns

### Async Context Manager Usage

The `gum` class is designed to be used as an async context manager:

```python
async with gum(user_name, model, Screen(model)) as gum_instance:
    await asyncio.Future()  # Run forever
```

This ensures proper initialization (`__aenter__`) and cleanup (`__aexit__`) of:
- Database connections
- Observer tasks
- Batch processing loops
- Attention monitoring threads

### Database Session Management

Always use async session context:

```python
async with self.Session() as session:
    # Database operations
    await session.commit()
```

### LLM Structured Outputs

All LLM calls use OpenAI's structured output with Pydantic schemas:

```python
response = await self.client.beta.chat.completions.parse(
    model=self.model,
    messages=messages,
    response_format=get_schema(PropositionSchema.model_json_schema())
)
```

### Observer Updates

Observers push updates via async queue:

```python
update = Update(content=text, content_type="input_text")
await self.update_queue.put(update)
```

## Platform Notes

### macOS-Specific Dependencies

- `pyobjc-framework-Quartz`: Window management and display bounds
- AppleScript via `osascript`: Active app detection
- Accessibility permissions required for `pynput` keyboard/mouse monitoring
- Screen recording permissions required for `mss` screenshots

### Permission Requirements

Before running GUM, grant Terminal (or your terminal app):
1. **Accessibility**: System Settings → Privacy & Security → Accessibility
2. **Screen Recording**: System Settings → Privacy & Security → Screen Recording

You may need to restart the terminal after granting permissions.

## Data Storage

GUM stores all data in `~/.cache/gum/`:
- `gum.db`: SQLite database with observations and propositions
- `batches/`: Persistent queue for observation batching
- `screenshots/`: Captured screenshots (if Screen observer configured to save)

Reset cache: `gum --reset-cache`

## Related Projects

- **dashboard/**: Next.js frontend for visualizing propositions and observations
- **my-app/**: Alternative Next.js application (appears to be prototype)
- **docs/**: MkDocs documentation source files
