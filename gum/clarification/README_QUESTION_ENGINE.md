# Clarifying Question Engine

## Overview

The Clarifying Question Engine generates targeted clarifying questions for propositions flagged by the clarification detection system. For each flagged proposition and factor, it produces:

1. **A clarifying question** - A polite, neutral question addressing the specific concern
2. **Reasoning** - A brief explanation (≤30 words) of why the question was asked
3. **Evidence citations** - References to observations that triggered the factor

## Quick Start

### Installation

```bash
# The engine is part of the gum package
cd /path/to/gum-elicitation
pip install -e .
```

### Basic Usage

```bash
# Set your OpenAI API key
export OPENAI_API_KEY="your-api-key-here"

# Run the engine on flagged propositions
python -m gum.clarification.cli_question_engine \
    --source=file \
    --input-file=test_results_200_props/flagged_propositions.json \
    --output=clarifying_questions.jsonl
```

### Python API

```python
import asyncio
from openai import AsyncOpenAI
from gum.config import Config
from gum.clarification.question_engine import ClarifyingQuestionEngine

async def generate_questions():
    client = AsyncOpenAI(api_key="your-api-key")
    config = Config()
    
    engine = ClarifyingQuestionEngine(
        openai_client=client,
        config=config,
        input_source="file",
        input_file_path="flagged_propositions.json",
        output_path="questions.jsonl"
    )
    
    summary = await engine.run()
    print(f"Processed {summary['total_processed']} items")
    print(f"Success: {summary['successful']}, Failed: {summary['failed']}")

asyncio.run(generate_questions())
```

## Architecture

### Module Structure

```
gum/clarification/
├── question_config.py          # Factor mappings and configuration
├── question_prompts.py         # Prompt templates and few-shot examples
├── question_validator.py       # Validation rules
├── question_loader.py          # Input loading (file/DB)
├── question_generator.py       # Core generation logic
├── question_engine.py          # Pipeline orchestrator
└── cli_question_engine.py      # Command-line interface
```

### Data Flow

```
Input (JSON/DB)
    ↓
question_loader.py → Load & normalize propositions
    ↓
question_engine.py → Expand into (prop, factor) pairs
    ↓
question_generator.py → Generate question + reasoning
    ↓
question_validator.py → Validate output
    ↓
question_engine.py → Write JSONL output
    ↓
Output (JSONL) + Summary
```

## Generation Methods

The engine uses two methods for generating questions:

### 1. Few-Shot Generation (Factors 3, 6, 8, 11)

**Used for**: Inferred Intent, Opacity, Privacy, Ambiguity

**Approach**: Provides 2-3 example questions to guide the model

**Example** (Factor 3 - Inferred Intent):
```
Proposition: "Arnav values communication with friends."
Question: "When you messaged those contacts, was it mostly to coordinate plans or to socialize?"
Reasoning: "This proposition infers motive from messaging patterns; clarifying confirms the actual intent."
```

### 2. Controlled QG (Factors 1, 2, 4, 5, 7, 9, 10, 12)

**Used for**: Identity Mismatch, Surveillance, Face Threat, Over-Positive, Generalization, Actor-Observer, Reputation Risk, Tone Imbalance

**Approach**: Structured prompts with politeness constraints and validation

**Example** (Factor 5 - Over-Positive):
```
Proposition: "Arnav is an exceptional problem solver."
Question: "The system described you as 'exceptional'. Does this feel accurate, or would you prefer a milder description?"
Reasoning: "The proposition uses strong praise that may not match self-view; asking allows correction."
```

## Factor-Specific Guidelines

| Factor | Method | Key Concern | Question Pattern |
|--------|--------|-------------|------------------|
| 1. Identity Mismatch | Controlled QG | Trait vs behavior | "Is this typical for you, or specific to this situation?" |
| 2. Surveillance | Controlled QG | Detail level consent | "Should we keep this level of detail or generalize?" |
| 3. Inferred Intent | Few-shot | Disambiguate motives | "Was it to X or Y?" |
| 4. Face Threat | Controlled QG | Soften criticism | "Could you explain what led to that view?" |
| 5. Over-Positive | Controlled QG | Tone down praise | "Does 'exceptional' feel accurate, or prefer milder?" |
| 6. Opacity | Few-shot | Request evidence | "What specific behaviors led to this?" |
| 7. Generalization | Controlled QG | Check scope | "Does this happen consistently, or are there exceptions?" |
| 8. Privacy | Few-shot | Ask consent | "Would you prefer to discuss this more privately?" |
| 9. Actor-Observer | Controlled QG | Situational context | "Do circumstances influenced this, or is it typical?" |
| 10. Reputation Risk | Controlled QG | Public visibility | "Would you be comfortable if others saw this?" |
| 11. Ambiguity | Few-shot | Clarify meaning | "Do you mean X, Y, or Z?" |
| 12. Tone Imbalance | Controlled QG | Match intent | "Would softer language be more appropriate?" |

## Input Format

The engine expects flagged propositions in JSON format:

```json
[
  {
    "prop_id": 77,
    "prop_text": "Arnav values communication with friends.",
    "triggered_factors": ["inferred_intent", "opacity"],
    "observations": [
      {
        "id": 451,
        "observation_text": "User messaged multiple contacts on WhatsApp"
      }
    ],
    "prop_reasoning": "Based on messaging patterns observed"
  }
]
```

## Output Format

The engine produces JSONL output (one JSON object per line):

```jsonl
{"prop_id": 77, "factor": "inferred_intent", "question": "When you messaged those contacts, was it mostly to coordinate plans or to socialize?", "reasoning": "This proposition infers motive from messaging patterns; clarifying confirms the actual intent.", "evidence": ["obs_451: User messaged multiple contacts on WhatsApp"], "prop_text": "Arnav values communication with friends.", "timestamp": "2025-11-01T10:30:00"}
```

## Validation Rules

### Question Validation

- ✅ Single question mark (one focused question)
- ✅ Polite tone (uses "could", "would", "might", etc.)
- ✅ Non-leading (avoids "didn't you", "since you", etc.)
- ✅ Length: 10-200 characters
- ❌ Multiple questions
- ❌ Assumptive language
- ❌ Commands instead of questions

### Reasoning Validation

- ✅ Length: 5-30 words (soft), 5-40 words (hard)
- ✅ Explains why question was asked
- ❌ Placeholder text (TODO, TBD, etc.)
- ❌ Too brief (<5 words)
- ❌ Too long (>40 words)

### Evidence Validation

- ✅ Format: "obs_{id}: {text}"
- ✅ Referenced observations exist
- ✅ Empty list (for factors without specific observations)
- ❌ Invalid format
- ❌ Non-existent observation IDs

## CLI Options

```bash
python -m gum.clarification.cli_question_engine [OPTIONS]

Options:
  --source TEXT           Input source: 'file' or 'db' [default: file]
  --input-file TEXT       Path to flagged_propositions.json
  --output TEXT           Output JSONL file path [default: test_results_200_props/clarifying_questions.jsonl]
  --prop-ids TEXT         Comma-separated prop IDs to process (e.g., "77,200,421")
  --factor-ids TEXT       Comma-separated factor IDs to process (e.g., "3,6,8")
  --api-key TEXT          OpenAI API key (or set OPENAI_API_KEY env var)
  --model TEXT            Model to use [default: gpt-4]
  --verbose               Enable verbose logging
```

### Examples

```bash
# Process all propositions
python -m gum.clarification.cli_question_engine --source=file

# Process specific propositions
python -m gum.clarification.cli_question_engine --prop-ids=77,200,421

# Process specific factors only
python -m gum.clarification.cli_question_engine --factor-ids=3,6,8,11

# Use GPT-3.5 Turbo (faster, cheaper)
python -m gum.clarification.cli_question_engine --model=gpt-3.5-turbo

# Verbose logging
python -m gum.clarification.cli_question_engine --verbose
```

## Error Handling

The engine implements graceful degradation:

### Retry Logic

1. **API Errors**: Exponential backoff, 3 retries (1s, 2s, 4s)
2. **Validation Failures**: Retry with feedback, 2 retries
3. **Individual Item Failures**: Log error, continue processing

### Error Types

| Error Type | Response | Tracked In |
|------------|----------|------------|
| API timeout | Retry 3x, then mark failed | `generation_errors` |
| Validation failure | Retry 2x, then mark failed | `validation_errors` |
| Invalid JSON response | Retry 3x, then mark failed | `generation_errors` |
| Missing input file | Fatal error, exit | N/A |
| Invalid factor ID | Log warning, skip | `failures` list |

### Summary Output

```json
{
  "total_processed": 150,
  "successful": 145,
  "failed": 5,
  "validation_errors": 3,
  "generation_errors": 2,
  "output_file": "clarifying_questions.jsonl",
  "elapsed_seconds": 187.5,
  "failures": [
    {
      "prop_id": 77,
      "factor": "inferred_intent",
      "error": "API timeout after 3 retries",
      "error_type": "generation"
    }
  ]
}
```

## Performance

### Expected Throughput

| Configuration | Items/Second | Notes |
|---------------|--------------|-------|
| Single-threaded | 0.2-0.5 | ~2-5s per item |
| Batch (5 concurrent) | 1.0-2.5 | Default concurrency |
| Batch (10 concurrent) | 2.0-4.0 | Requires API quota |

### Optimization Tips

1. **Use GPT-3.5 Turbo**: 2-3x faster than GPT-4
2. **Increase concurrency**: Modify `BatchQuestionGenerator.max_concurrent`
3. **Filter early**: Use `--prop-ids` or `--factor-ids` to process subset
4. **Batch processing**: Process in chunks for large datasets

### Memory Usage

- **Small datasets** (<100 items): ~50 MB
- **Medium datasets** (100-1000 items): ~100 MB
- **Large datasets** (>1000 items): ~200 MB

## Testing

### Run Tests

```bash
# Install pytest
pip install pytest pytest-asyncio

# Run all tests
pytest tests/test_question_*.py -v

# Run specific test file
pytest tests/test_question_config.py -v

# Run with coverage
pytest tests/test_question_*.py --cov=gum.clarification --cov-report=html
```

### Test Coverage

- **Unit tests**: 180+ tests across 5 modules
- **Integration tests**: 18 end-to-end scenarios
- **Property-based tests**: Invariant checking
- **Line coverage**: >90% (target)

## Troubleshooting

### Common Issues

#### 1. "No module named pytest"

```bash
pip install pytest pytest-asyncio
```

#### 2. "OpenAI API key not provided"

```bash
export OPENAI_API_KEY="your-key-here"
# Or use --api-key flag
```

#### 3. "File not found: flagged_propositions.json"

```bash
# Check file exists
ls test_results_200_props/flagged_propositions.json

# Or specify full path
--input-file=/full/path/to/file.json
```

#### 4. High validation failure rate

- Review generated questions manually
- Check if prompts need adjustment
- Consider increasing retry limit in code
- Verify few-shot examples are appropriate

#### 5. Slow processing

- Use `--model=gpt-3.5-turbo` for faster generation
- Increase concurrency (modify `max_concurrent` in code)
- Check network latency
- Verify API rate limits not exceeded

## Development

### Adding New Factors

1. **Update config** (`question_config.py`):
   ```python
   FACTOR_METHOD_MAP[13] = "few_shot"  # or "controlled_qg"
   FACTOR_NAMES[13] = "new_factor_name"
   FACTOR_DESCRIPTIONS[13] = "Human-readable description"
   ```

2. **Add few-shot examples** (if using few-shot):
   ```python
   FEW_SHOT_EXAMPLES[13] = [
       {
           "prop": "Example proposition",
           "question": "Example question?",
           "reasoning": "Example reasoning.",
           "evidence": []
       }
   ]
   ```

3. **Write tests**:
   ```python
   def test_new_factor():
       assert get_factor_name(13) == "new_factor_name"
   ```

4. **Update documentation**: Add to factor table above

### Code Style

- **Formatting**: Follow PEP 8
- **Type hints**: Use for all function signatures
- **Docstrings**: Google-style docstrings
- **Logging**: Use structured logging with context

### Contributing

1. Write tests for new features
2. Ensure no linter errors (`flake8`, `mypy`)
3. Update documentation
4. Run full test suite before committing

## References

- **Implementation Plan**: `CLARIFYING_QUESTION_ENGINE_IMPLEMENTATION.md`
- **Robustness Documentation**: `CLARIFYING_QUESTION_ENGINE_ROBUSTNESS.md`
- **Clarification Detection**: `CLARIFICATION_DETECTION_README.md`

## License

Same as parent project (see LICENSE file).

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review robustness documentation
3. Check test files for examples
4. Review implementation plan for design details

