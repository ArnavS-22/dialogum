# Clarifying Question + Reasoning Engine - Implementation Plan

## Overview

This document outlines the complete implementation plan for generating clarifying questions and reasoning explanations for flagged propositions from the clarification detection engine.

## System Purpose

When the clarification detector flags a proposition (e.g., "Arnav is an exceptional problem solver"), the system generates:

- A single clarifying question addressing the specific factor
- A short reasoning line explaining why that question was asked
- Evidence citations showing which observations triggered the factor

## System Architecture

```
gum/clarification/
├── question_engine.py          # Main engine (entry point)
├── question_generator.py        # Generation logic (few-shot, controlled)
├── question_validator.py        # Validation rules
├── question_prompts.py          # Prompt templates and few-shot examples
├── question_config.py          # Factor-to-method mapping, constants
├── question_loader.py           # Input loading (DB/file)
└── cli_question_engine.py       # CLI entry point
```

## Module 1: `question_config.py`

### Purpose
Central configuration and mappings

### Contents

```python
# Factor ID to method mapping
FACTOR_METHOD_MAP = {
    1: "controlled_qg",   # Identity Mismatch
    2: "controlled_qg",   # Surveillance
    3: "few_shot",        # Inferred Intent
    4: "controlled_qg",  # Face Threat
    5: "controlled_qg",  # Over-Positive
    6: "few_shot",        # Opacity
    7: "controlled_qg",  # Generalization
    8: "few_shot",        # Privacy
    9: "controlled_qg",  # Actor-Observer
    10: "controlled_qg", # Reputation Risk
    11: "few_shot",       # Ambiguity
    12: "controlled_qg"  # Tone Imbalance
}

# Factor names (for prompts/logging)
FACTOR_NAMES = {
    1: "identity_mismatch",
    2: "surveillance",
    3: "inferred_intent",
    4: "face_threat",
    5: "over_positive",
    6: "opacity",
    7: "generalization",
    8: "privacy",
    9: "actor_observer",
    10: "reputation_risk",
    11: "ambiguity",
    12: "tone_imbalance"
}

# Human-readable descriptions (for prompts)
FACTOR_DESCRIPTIONS = {
    1: "Identity Mismatch - The proposition labels you with a personality trait rather than describing behavior",
    2: "Surveillance - The proposition includes overly specific details that feel invasive",
    3: "Inferred Intent - The proposition assumes it knows WHY you did something",
    4: "Face Threat - The proposition is socially critical or disapproving",
    5: "Over-Positive - The proposition gives unexpectedly strong praise",
    6: "Opacity - The proposition makes a confident claim but lacks clear evidence",
    7: "Generalization - The proposition uses absolute language (always, never, all)",
    8: "Privacy - The proposition touches sensitive domains (health, finance, relationships)",
    9: "Actor-Observer Mismatch - The proposition attributes a trait without situational context",
    10: "Reputation Risk - The proposition could affect your social image if shared",
    11: "Ambiguity - The proposition has multiple possible interpretations",
    12: "Tone Imbalance - The proposition's assertiveness doesn't match the evidence"
}

# Validation thresholds
MAX_REASONING_WORDS = 30
HARD_REASONING_LIMIT = 40
MIN_QUESTION_LENGTH = 10
MAX_QUESTION_LENGTH = 200
```

### Functions

- `get_method_for_factor(factor_id: int) -> str`
- `get_factor_name(factor_id: int) -> str`
- `get_factor_description(factor_id: int) -> str`
- `get_factor_id_from_name(factor_name: str) -> Optional[int]`

## Module 2: `question_prompts.py`

### Purpose
Prompt templates and few-shot examples for question generation

### Few-Shot Examples

Each factor using few-shot method needs 2-3 example question/reasoning pairs:

```python
FEW_SHOT_EXAMPLES = {
    3: [  # Inferred Intent
        {
            "prop": "Arnav values communication with friends...",
            "question": "When you messaged those contacts, was it mostly to coordinate plans or to socialize?",
            "reasoning": "This proposition infers motive from messaging patterns; clarifying confirms the actual intent.",
            "evidence": ["obs_451: multiple WhatsApp Web sessions"]
        },
        # ... 2-3 more examples
    ],
    6: [  # Opacity
        {
            "prop": "Arnav may undervalue less quantifiable aspects...",
            "question": "Could you clarify what you mean by 'less quantifiable aspects'?",
            "reasoning": "The phrase is abstract; clarifying grounds the claim in specific examples.",
            "evidence": []
        },
        # ... 2-3 more examples
    ],
    8: [  # Privacy
        {
            "prop": "Arnav is editing a document about personal health...",
            "question": "Would you prefer to discuss this more privately, or is this detail level okay?",
            "reasoning": "This touches sensitive domains; asking checks consent level.",
            "evidence": ["obs_176: editing health document"]
        },
        # ... 2-3 more examples
    ],
    11: [  # Ambiguity
        {
            "prop": "Arnav is focused on development...",
            "question": "When you say 'focused on development', do you mean coding tasks, project planning, or learning new skills?",
            "reasoning": "The term 'development' has multiple interpretations; clarifying specifies which meaning applies.",
            "evidence": []
        },
        # ... 2-3 more examples
    ]
}
```

### Controlled QG Prompts

```python
CONTROLLED_QG_SYSTEM_PROMPT = """
You are generating a clarifying question for a flagged proposition.

The proposition is a statement the SYSTEM made about the user, not something the user said.

Guidelines:
- Ask ONE neutral, clarifying question
- Use polite, non-judgmental language
- Avoid assumptive phrasing ("didn't you", "since you", "you always")
- Prefer "could", "would", "might", "perhaps" for politeness
- Do not make multiple asks in one question
- Be specific but respectful
- Reference the system's observation: "We observed that..." or "The system noted..."

Factor: {factor_description}
Proposition: {proposition_text}
Observations: {observation_summary}

Generate a clarifying question and a brief reasoning (≤30 words) explaining why you asked.
"""

CONTROLLED_QG_USER_PROMPT = """
Return JSON:
{
    "question": "...",
    "reasoning": "..."
}
"""
```

### Functions

- `get_few_shot_examples(factor_id: int) -> List[Dict]`
- `build_few_shot_prompt(prop_text, factor_id, factor_description, observation_summary) -> str`
- `build_controlled_qg_prompt(prop_text, factor_description, observation_summary) -> str`

## Module 3: `question_generator.py`

### Purpose
Generate questions using the three methods

### Class: `QuestionGenerator`

#### Main Entry Point

```python
async def generate_question_pair(
    prop_id: int,
    prop_text: str,
    factor_id: int,
    observations: List[Observation],
    prop_reasoning: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main entry point: generates question + reasoning + evidence.
    
    Returns:
    {
        "prop_id": 77,
        "factor": "inferred_intent",
        "question": "...",
        "reasoning": "...",
        "evidence": ["obs_451: ..."]
    }
    """
    method = get_method_for_factor(factor_id)
    
    if method == "few_shot":
        return await self._generate_from_few_shot(
            prop_id, prop_text, factor_id, observations, prop_reasoning
        )
    elif method == "controlled_qg":
        return await self._generate_from_controlled_qg(
            prop_id, prop_text, factor_id, observations
        )
```

#### Few-Shot Generation

```python
async def _generate_from_few_shot(
    prop_id: int,
    prop_text: str,
    factor_id: int,
    observations: List[Observation],
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
    """
```

#### Controlled QG Generation

```python
async def _generate_from_controlled_qg(
    prop_id: int,
    prop_text: str,
    factor_id: int,
    observations: List[Observation],
    max_retries: int = 2
) -> Dict[str, Any]:
    """
    Generate using controlled QG (polite prompt + validation).
    
    Steps:
    1. Build controlled QG prompt
    2. Call LLM with JSON response format
    3. Parse JSON (question, reasoning)
    4. Run validation checks
    5. If validation fails, retry with adjusted prompt (max 2 retries)
    6. Extract evidence
    7. Return dict
    """
```

#### Helper Methods

- `_extract_evidence(observations, factor_id, limit=3) -> List[str]` - Extract evidence citations
- `_format_observation_summary(observations) -> str` - Format observations for prompts

## Module 4: `question_validator.py`

### Purpose
Validate generated questions and reasoning

### Class: `QuestionValidator`

#### Validation Methods

**`validate_question(question: str) -> Tuple[bool, List[str]]`**
- Checks: single focus, non-leading, appropriate length, polite tone
- Rejects: "didn't you", "why didn't you", "since you", "you always"

**`validate_reasoning(reasoning: str) -> Tuple[bool, List[str]]`**
- Checks: length ≤30 words (soft) or ≤40 (hard), mentions factor concern, no sensitive data

**`validate_evidence(evidence: List[str], observation_ids: List[int]) -> Tuple[bool, List[str]]`**
- Checks: observation IDs exist, format matches "obs_{id}: {summary}"

**`validate_full_output(output: Dict[str, Any]) -> Tuple[bool, List[str]]`**
- Validates complete output dict with all required fields

**`truncate_reasoning(reasoning: str, max_words: int = 30) -> str`**
- Truncates reasoning to max_words, adding ellipsis if truncated

### Validation Rules

- **Single-focus**: Only one question (count "?")
- **Non-leading**: No "didn't you", "why didn't you", "since you"
- **Polite tone**: Uses "could", "would", "might", "perhaps"
- **Reasoning length**: ≤30 words (soft cap), ≤40 words (hard limit)
- **Evidence format**: "obs_{id}: {summary}"

## Module 5: `question_loader.py`

### Purpose
Load flagged propositions from DB or file

### Functions

**`load_flagged_propositions(source: str = "file", file_path: Optional[str] = None, db_session: Optional[AsyncSession] = None) -> List[Dict[str, Any]]`**

- **source**: "file" or "db"
- **file_path**: Path to JSON file (default: `test_results_200_props/flagged_propositions.json`)
- **db_session**: Database session (required if source="db")

Returns list of flagged proposition dicts with:
- `prop_id`
- `prop_text`
- `triggered_factors` (list of factor names)
- `observations` (list of observation dicts or IDs)
- `prop_reasoning` (optional)

**`_load_from_db(session: AsyncSession) -> List[Dict[str, Any]]`**
- Query `ClarificationAnalysis` for flagged propositions
- Returns formatted list compatible with file format

**`_load_from_file(file_path: Optional[str] = None) -> List[Dict[str, Any]]`**
- Load flagged propositions from JSON file
- Default path: `test_results_200_props/flagged_propositions.json`

## Module 6: `question_engine.py`

### Purpose
Main orchestrator for the pipeline

### Class: `ClarifyingQuestionEngine`

#### Initialization

```python
def __init__(
    self,
    openai_client: AsyncOpenAI,
    config,
    input_source: str = "file",
    output_path: Optional[str] = None
):
```

#### Main Pipeline

```python
async def run(
    self,
    prop_ids: Optional[List[int]] = None,
    factor_ids: Optional[List[int]] = None,
    db_session: Optional[AsyncSession] = None
) -> Dict[str, Any]:
    """
    Main pipeline execution.
    
    Steps:
    1. Load flagged propositions
    2. Filter by prop_ids/factor_ids if provided
    3. For each (prop × factor):
        a. Generate question + reasoning + evidence
        b. Validate output
        c. If invalid, log warning and skip
        d. Append to results list
    4. Write JSONL output file
    5. Return stats summary
    
    Returns:
    {
        "total_processed": 150,
        "successful": 145,
        "failed": 5,
        "output_file": "test_results_200_props/clarifying_questions.jsonl",
        "failures": [...]
    }
    """
```

#### Helper Methods

- `_process_proposition(prop_data: Dict[str, Any]) -> List[Dict[str, Any]]` - Process single proposition
- `_convert_observations(observations: List[Dict]) -> List[Observation]` - Convert observation dicts to objects
- `_write_jsonl(results: List[Dict[str, Any]]) -> None` - Write results to JSONL file
- `_get_stats_summary(results, failures) -> Dict[str, Any]` - Generate statistics summary

## Module 7: `cli_question_engine.py`

### Purpose
Command-line interface

### Usage

```bash
python -m gum.clarification.cli_question_engine \
    --source=file \
    --output=test_results_200_props/clarifying_questions.jsonl \
    --prop-ids=77,200,421 \
    --factor-ids=3,6
```

### Arguments

- `--source`: "file" or "db" (default: "file")
- `--output`: Output JSONL file path (default: `test_results_200_props/clarifying_questions.jsonl`)
- `--prop-ids`: Comma-separated prop IDs to process
- `--factor-ids`: Comma-separated factor IDs to process
- `--input-file`: Path to flagged_propositions.json (overrides default)

## Output Schema

Each generated output follows this structure:

```json
{
  "prop_id": 77,
  "factor": "inferred_intent",
  "question": "When you messaged those contacts, was it mostly to coordinate plans or to socialize?",
  "reasoning": "This proposition infers motive from messaging patterns; clarifying confirms the actual intent.",
  "evidence": [
    "obs_451: multiple WhatsApp Web sessions on 2025-09-29",
    "obs_452: opened chat with 3 different contacts"
  ]
}
```

## Factor-to-Method Mapping

| Factor ID | Factor Name | Method | Why |
|-----------|-------------|--------|-----|
| 1 | Identity Mismatch | Controlled QG | Needs politeness to avoid trait labeling |
| 2 | Surveillance | Controlled QG | Needs consent-seeking language |
| 3 | Inferred Intent | Few-shot | Nuanced; examples guide disambiguation |
| 4 | Face Threat | Controlled QG | Needs softening to avoid offense |
| 5 | Over-Positive | Controlled QG | Needs nuanced phrasing adaptation to specific praise words |
| 6 | Opacity | Few-shot | Examples show how to ask for specifics |
| 7 | Generalization | Controlled QG | Needs adaptation to specific absolutist language |
| 8 | Privacy | Few-shot | Context-sensitive; examples guide framing |
| 9 | Actor-Observer | Controlled QG | Needs open-ended, context-aware phrasing |
| 10 | Reputation Risk | Controlled QG | Needs adaptation to sensitivity level of claim |
| 11 | Ambiguity | Few-shot | Examples show disambiguation patterns |
| 12 | Tone Imbalance | Controlled QG | Needs tone-softening language |

## Methodology Details

### Few-Shot Method (Factors 3, 6, 8, 11)

- Provides 2-3 example question/reasoning pairs
- LLM generates similar question for current proposition
- Examples guide the model on appropriate phrasing and disambiguation

### Controlled QG Method (Factors 1, 2, 4, 5, 7, 9, 10, 12)

- Generates with politeness/neutrality constraints in prompt
- Factor-specific prompt constraints tailored to each factor's needs
- Validates output (single focus, non-leading, polite tone)
- Retries up to 2 times if validation fails
- Adjusts prompt based on validation failures
- Adapts to specific proposition wording and context

## Factor-Specific Implementation Guide

### Factor 1: Identity Mismatch (Controlled QG)

**What it addresses:** Proposition labels user with a personality trait rather than describing behavior

**Question Goal:** Distinguish trait attribution from behavioral observation

**Prompt Constraints:**
- Avoid labeling personality ("you are X", "you're a procrastinator")
- Ask about trait vs. behavior distinction
- Use polite phrasing ("could", "would", "might")
- Reference system observation: "We observed that..."

**Validation Checks:**
- ❌ Reject: "You're clearly a perfectionist" (trait labeling)
- ✅ Accept: "Would you say your current focus is on themes, structure, or both?"
- ✅ Accept: "Do you see yourself as structured in general, or is this just for academics?"

**Example Good Question:** "Would you say your current approach reflects your typical style, or was this specific to this situation?"

**Reasoning Pattern:** "The proposition turns a context-specific behavior into a global trait; asking distinguishes scope."

---

### Factor 2: Surveillance (Controlled QG)

**What it addresses:** Proposition includes overly specific details that feel invasive

**Question Goal:** Ask consent about detail level, offer generalization option

**Prompt Constraints:**
- Ask permission explicitly ("do you want", "should we")
- Acknowledge specificity explicitly
- Offer choice between specific and general
- Reference system observation: "We observed that..."

**Validation Checks:**
- ❌ Reject: "You're sharing too much detail" (judgmental)
- ✅ Accept: "Do you want us to record the specific project title, or should we generalize it?"
- ✅ Accept: "We noted specific details about your work. Would you prefer we keep this level of detail or generalize it?"

**Example Good Question:** "Do you want us to record the specific project title, or should we generalize it?"

**Reasoning Pattern:** "This references exact project details, which may feel invasive; asking checks consent."

---

### Factor 3: Inferred Intent (Few-Shot)

**What it addresses:** Proposition assumes it knows WHY the user did something

**Question Goal:** Disambiguate motives/goals, ask what the actual intent was

**Few-Shot Examples Should Show:**
- Questions that ask about motivation without assuming
- Questions that offer alternatives ("was it X or Y?")
- Questions that reference observed behavior

**Example Good Question:** "When you messaged those contacts, was it mostly to coordinate plans or to socialize?"

**Reasoning Pattern:** "This proposition infers motive from messaging patterns; clarifying confirms the actual intent."

**Key Instruction:** Never assume you know WHY. Always ask what the user's actual goal or motivation was.

---

### Factor 4: Face Threat (Controlled QG)

**What it addresses:** Proposition is socially critical or disapproving

**Question Goal:** Offer rephrase option, soften criticism, frame neutrally

**Prompt Constraints:**
- Offer alternative framing
- Use softening language ("perhaps", "might")
- Frame as "I might see this differently"
- Never be accusatory or judgmental

**Validation Checks:**
- ❌ Reject: "You're wrong about this" (confrontational)
- ❌ Reject: "You're careless" (direct criticism)
- ✅ Accept: "I might see this differently—could you explain what led you to that view?"
- ✅ Accept: "Would you prefer we phrase this differently, or does this match your perspective?"

**Example Good Question:** "I might see this differently—could you explain what led you to that view?"

**Reasoning Pattern:** "The proposition may be socially critical; asking allows user to correct or reframe."

---

### Factor 5: Over-Positive (Controlled QG)

**What it addresses:** Proposition gives unexpectedly strong praise

**Question Goal:** Offer toned-down alternative phrasing, adapt to specific praise words

**Prompt Constraints:**
- Acknowledge the praise word explicitly ("exceptional", "remarkable", "outstanding")
- Offer milder alternatives that match the proposition context
- Use softening language ("perhaps", "might", "could")
- Reference system observation: "We observed that..." or "The system described you as..."

**Validation Checks:**
- ❌ Reject: "You're not that great" (dismissive)
- ✅ Accept: "The system described you as 'exceptional'. Does this feel accurate, or would you prefer a milder description?"
- ✅ Accept: "We noted strong praise in this observation. Would you prefer we phrase this more modestly?"

**Example Good Question:** "The system described you as 'exceptional'. Does this feel accurate, or would you prefer a milder description?"

**Reasoning Pattern:** "The proposition uses strong praise that may not match self-view; asking allows correction."

**Key Instruction:** Adapt phrasing to the specific praise word used in the proposition. Different praise words may need different softening approaches.

---

### Factor 6: Opacity (Few-Shot)

**What it addresses:** Proposition makes a confident claim but lacks clear evidence

**Question Goal:** Ask for concrete evidence or clarification of vague reasoning

**Few-Shot Examples Should Show:**
- Questions that ask "what do you mean by X?"
- Questions that request specific examples
- Questions that clarify abstract phrases

**Example Good Question:** "Could you clarify what you mean by 'less quantifiable aspects'?"

**Reasoning Pattern:** "The phrase is abstract; clarifying grounds the claim in specific examples."

**Key Instruction:** Ask for concrete evidence or specific examples to support vague claims.

---

### Factor 7: Generalization (Controlled QG)

**What it addresses:** Proposition uses absolute language (always, never, all)

**Question Goal:** Check scope/frequency, ask about exceptions, adapt to specific absolutist words

**Prompt Constraints:**
- Identify the specific absolutist word ("always", "never", "all", "every", "none")
- Ask about scope/frequency in a way that matches the word used
- Reference system observation: "We observed that..."
- Use open-ended phrasing that allows nuanced response

**Validation Checks:**
- ❌ Reject: "You don't always do that" (confrontational)
- ✅ Accept: "We observed that 'Arnav always interrupts meetings'. Does this happen consistently, or are there exceptions?"
- ✅ Accept: "The system noted this happens 'every time'. Would you say that's accurate, or are there situations where it differs?"

**Example Good Question:** "We observed that 'Arnav always interrupts meetings'. Does this happen consistently, or are there exceptions?"

**Reasoning Pattern:** "The proposition uses absolutist language; asking clarifies scope and frequency."

**Key Instruction:** Adapt the question to the specific absolutist word. "Always" vs "never" vs "all" may need different phrasings.

---

### Factor 8: Privacy (Few-Shot)

**What it addresses:** Proposition touches sensitive domains (health, finance, relationships)

**Question Goal:** Ask about sensitivity/consent, offer more private discussion

**Few-Shot Examples Should Show:**
- Questions that ask consent about sensitive topics
- Questions that offer privacy options
- Questions that acknowledge sensitivity respectfully

**Example Good Question:** "Would you prefer to discuss this more privately, or is this detail level okay?"

**Reasoning Pattern:** "This touches sensitive domains; asking checks consent level."

**Key Instruction:** Always acknowledge sensitivity and offer choice about privacy level.

---

### Factor 9: Actor-Observer (Controlled QG)

**What it addresses:** Proposition attributes a trait without situational context

**Question Goal:** Distinguish situational vs. trait causes, ask about circumstances

**Prompt Constraints:**
- Must ask about circumstances/context
- Not assuming trait ("do you think circumstances influenced...")
- Open-ended (not yes/no)
- Reference system observation: "We observed that..."

**Validation Checks:**
- ❌ Reject: "You're always like this" (assumes trait)
- ✅ Accept: "Do you think circumstances influenced that behavior, or is this typical for you?"
- ✅ Accept: "Was this behavior specific to the situation, or does it reflect your usual approach?"

**Example Good Question:** "Do you think circumstances influenced that behavior, or is this typical for you?"

**Reasoning Pattern:** "The proposition attributes a trait without situational context; asking distinguishes dispositional from situational causes."

---

### Factor 10: Reputation Risk (Controlled QG)

**What it addresses:** Proposition could affect social image if shared

**Question Goal:** Ask about public visibility comfort, adapt to sensitivity level of claim

**Prompt Constraints:**
- Acknowledge the potential reputation impact explicitly
- Adapt phrasing based on how sensitive the claim is (mild vs serious)
- Offer framing options ("would you be comfortable", "should we phrase this differently")
- Reference system observation: "We noted that..."

**Validation Checks:**
- ❌ Reject: "This would embarrass you" (assumptive)
- ✅ Accept: "We noted that 'Arnav struggles with time management'. Would you be comfortable if others saw this observation?"
- ✅ Accept: "This observation could affect how others see you. Would you prefer we keep this private, or are you okay with it being visible?"

**Example Good Question:** "We noted that 'Arnav struggles with time management'. Would you be comfortable if others saw this observation?"

**Reasoning Pattern:** "The proposition could affect reputation if shared; asking checks public visibility comfort."

**Key Instruction:** Adapt tone based on how reputation-threatening the claim is. More sensitive claims need softer, more cautious phrasing.

---

### Factor 11: Ambiguity (Few-Shot)

**What it addresses:** Proposition has multiple possible interpretations

**Question Goal:** Clarify interpretation or referent, ask which meaning applies

**Few-Shot Examples Should Show:**
- Questions that list multiple interpretations
- Questions that ask "do you mean X or Y?"
- Questions that clarify vague terms

**Example Good Question:** "When you say 'focused on development', do you mean coding tasks, project planning, or learning new skills?"

**Reasoning Pattern:** "The term 'development' has multiple interpretations; clarifying specifies which meaning applies."

**Key Instruction:** Identify ambiguous terms and offer multiple interpretations to choose from.

---

### Factor 12: Tone Imbalance (Controlled QG)

**What it addresses:** Proposition's assertiveness doesn't match the evidence

**Question Goal:** Ask if tone matches intent, offer to soften wording

**Prompt Constraints:**
- Must ask about tone preference
- Offers adjustment ("would it be fair to say...")
- Not presuming ("you're too confident" - bad)
- Reference system observation: "We observed that..."

**Validation Checks:**
- ❌ Reject: "You're too confident" (judgmental)
- ✅ Accept: "Would it be fair to say you're somewhat X?"
- ✅ Accept: "Does this level of certainty match how you'd describe it, or would you prefer softer language?"

**Example Good Question:** "Would it be fair to say you're somewhat X?"

**Reasoning Pattern:** "The proposition's assertiveness may not match the evidence; asking checks if tone should be adjusted."

---

## Factor-Specific Summary Table

| Factor | Method | Key Question Goal | Critical Constraint |
|--------|--------|-------------------|---------------------|
| 1. Identity Mismatch | Controlled QG | Distinguish trait vs behavior | Avoid trait labeling |
| 2. Surveillance | Controlled QG | Ask consent for detail level | Offer choice, not judgment |
| 3. Inferred Intent | Few-shot | Disambiguate motives | Never assume WHY |
| 4. Face Threat | Controlled QG | Offer rephrase option | Soften criticism |
| 5. Over-Positive | Controlled QG | Offer milder phrasing | Adapt to specific praise words |
| 6. Opacity | Few-shot | Ask for concrete evidence | Request specifics |
| 7. Generalization | Controlled QG | Check scope/frequency | Adapt to specific absolutist words |
| 8. Privacy | Few-shot | Ask about sensitivity | Acknowledge sensitivity |
| 9. Actor-Observer | Controlled QG | Distinguish situational vs trait | Ask about circumstances |
| 10. Reputation Risk | Controlled QG | Ask about public visibility | Adapt to sensitivity level |
| 11. Ambiguity | Few-shot | Clarify interpretation | Offer multiple meanings |
| 12. Tone Imbalance | Controlled QG | Ask if tone matches intent | Offer softer language |

## Data Flow

```
1. Load Input
   └─> question_loader.py
       ├─ From file: flagged_propositions.json
       └─ From DB: ClarificationAnalysis query

2. For Each (Prop × Factor):
   └─> question_generator.py
       ├─ Determine method (few-shot/controlled)
       ├─ Generate question + reasoning
       └─ Extract evidence

3. Validate Output
   └─> question_validator.py
       ├─ Validate question
       ├─ Validate reasoning
       └─ Validate evidence

4. Write Results
   └─> question_engine.py
       └─> Write JSONL file

5. Return Stats
   └─> Summary with counts, failures, etc.
```

## Error Handling

- **Generation failures**: Log error, skip that item, continue processing
- **Validation failures**: Log warning, skip that item (or retry for controlled QG)
- **API errors**: Retry with exponential backoff (max 3 retries)
- **Invalid input**: Log error, skip, continue

## File Structure Summary

```
gum/clarification/
├── question_engine.py          # Main orchestrator (~250 lines)
├── question_generator.py        # Generation logic (~450 lines)
├── question_validator.py        # Validation rules (~200 lines)
├── question_prompts.py          # Prompts & templates (~350 lines)
├── question_config.py          # Config & mappings (~150 lines)
├── question_loader.py           # Input loading (~150 lines)
└── cli_question_engine.py       # CLI entry point (~80 lines)

Total: ~1480 lines of code
```

## Implementation Order

1. **`question_config.py`** - Mappings and constants
2. **`question_prompts.py`** - Templates and examples
3. **`question_validator.py`** - Validation logic
4. **`question_loader.py`** - Input loading
5. **`question_generator.py`** - Generation methods
6. **`question_engine.py`** - Main orchestrator
7. **`cli_question_engine.py`** - CLI interface

## Testing Strategy

### Unit Tests

- `test_question_generator.py` - Test each generation method
- `test_question_validator.py` - Test validation rules
- `test_question_prompts.py` - Test prompt building
- `test_question_loader.py` - Test input loading

### Integration Test

- `test_question_engine.py` - End-to-end with sample data

## Dependencies

- `openai` (AsyncOpenAI client)
- `sqlalchemy` (for DB access)
- `json` (for JSONL output)
- `textwrap` (for evidence summarization)
- Existing: `gum.models`, `gum.clarification_models`

## Output File

**Default location:** `test_results_200_props/clarifying_questions.jsonl`

**Format:** JSONL (one JSON object per line)

**Contents:** All successfully generated question pairs with reasoning and evidence

## Key Design Decisions

1. **All factors use LLM generation**: No hard templates - all questions generated via controlled QG or few-shot for research-quality adaptability
2. **Controlled QG for majority**: 8 factors use controlled QG for nuanced, context-aware generation
3. **Few-shot for disambiguation**: 4 factors use few-shot where examples guide complex disambiguation patterns
4. **Evidence format**: Standardized as "obs_{id}: {summary}"
5. **Validation**: Comprehensive checks for quality, politeness, and correctness
6. **Error handling**: Graceful degradation - log errors but continue processing
7. **Retry logic**: Only for controlled QG factors when validation fails

## Next Steps

1. Implement modules in order listed above
2. Write few-shot examples for factors 3, 6, 8, 11
3. Test with sample flagged propositions
4. Validate output quality
5. Integrate with Gates system for user-facing review

