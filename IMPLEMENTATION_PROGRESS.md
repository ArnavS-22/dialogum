# GUM Ambiguity Detection System - Implementation Progress

## Overview
Building a robust ambiguity detection and urgency assessment system for GUM (Grounded Understanding of User Models) propositions, inspired by UCSB's entropy-based approach for question answering.

**Goal**: Detect ambiguity in user behavior propositions to enable proactive clarifying dialogues via GATE (Grounded Adaptive Transparent Elicitation).

---

## ✅ COMPLETED (Steps 1-2)

### 1. Database Schema Extensions ✅
**Files Created:**
- `gum/ambiguity_models.py` - New SQLAlchemy models
- `gum/ambiguity_config.py` - Configuration and thresholds
- `gum/migrate_ambiguity_tables.py` - Migration script

**Database Tables Created:**
- `ambiguity_analyses`: Stores interpretations, clusters, entropy scores
- `urgency_assessments`: Stores URGENT/SOON/LATER tags and reasoning
- `clarification_dialogues`: Tracks GATE questions and user responses

**Test Results:**
```
✅ Migration verification passed!
   ✓ ambiguity_analyses
   ✓ urgency_assessments  
   ✓ clarification_dialogues
   ✓ Found 8 indexes
```

### 2. Interpretation Generation Module ✅
**Files Created:**
- `gum/ambiguity/interpretation_generator.py` - Core module
- `test_interpretation_module.py` - Comprehensive tests

**Features:**
- Synchronous and asynchronous interpretation generation
- Batch processing support
- Structured parsing of LLM responses
- Error handling and metadata tracking
- Storage formatting for database

**Test Results:**
```
✅ Synchronous Test: PASS
   - Generated 4 distinct interpretations
   - Tokens used: 740
   - Quality: High (meaningful distinctions)

✅ Asynchronous Test: PASS
   - Processed 3 propositions concurrently
   - All generated 3-4 interpretations each
   - No errors
```

**Example Output:**
For proposition: "Dhruv Yadati prefers working with Python and appears to rely on terminal commands..."

Generated 4 interpretations:
1. Uses Python as main language for regular project work
2. Prefers Python due to familiarity and need for system interaction
3. Chooses Python over Node.js for ease of terminal commands
4. Work involves backend programming or data analysis tasks

Each with distinct distinguishing features!

---

## 🔄 IN PROGRESS (Steps 3-15)

### 3. Answer Collection Module
**Next Step**: Create `gum/ambiguity/answer_collector.py`

**Requirements:**
- Take interpretations as input
- Generate 8-10 answers per interpretation using LLM
- Use varied sampling (temperature 0.8)
- Use cheaper model (gpt-3.5-turbo) for cost efficiency
- Return structured answers grouped by interpretation

**Prompt Strategy:**
```
Given this interpretation of a user behavior proposition:
"{interpretation_text}"

Answer the question: "Is this an accurate understanding of the user?"
Provide a brief yes/no answer with 1-2 sentence explanation.
```

### 4. Semantic Clustering Module
**Next Step**: Create `gum/ambiguity/clustering.py`

**Requirements:**
- Use sentence-transformers for embeddings (all-MiniLM-L6-v2)
- Implement HDBSCAN for clustering (min_cluster_size=2)
- Fallback to KMeans if HDBSCAN gives poor results
- Return cluster assignments and cluster sizes

**Dependencies to Install:**
```bash
pip install sentence-transformers hdbscan umap-learn
```

### 5. Entropy Computation Module
**Next Step**: Create `gum/ambiguity/entropy_calculator.py`

**Requirements:**
- Compute Shannon entropy over cluster distribution
- Formula: H = -Σ(p_i * log2(p_i))
- Apply threshold (default: 0.8) for binary classification
- Support normalized entropy (H / log2(num_clusters))
- Return: entropy_score, is_ambiguous flag

**Threshold Calibration Plan:**
- Start with default: 0.8 (from UCSB + domain adjustment)
- Calibrate using labeled data (50+ propositions)
- Optimize for precision/recall trade-off

### 6. Urgency Detection Module
**Next Step**: Create `gum/ambiguity/urgency_detector.py`

**Heuristics:**
```python
urgency_score = (
    ambiguity_weight * entropy_score +
    confidence_weight * (1 - confidence/10) +
    temporal_weight * time_sensitivity_score
)

if urgency_score >= 0.7: URGENT
elif urgency_score >= 0.4: SOON
else: LATER
```

**Temporal Keywords:**
- SOON triggers: today, tomorrow, now, deadline, schedule
- Context analysis: recent propositions get higher weight

### 7. Pipeline Orchestrator
**Next Step**: Create `gum/ambiguity/pipeline.py`

**Flow:**
```
Proposition
  → Interpretation Generator (2-4 interpretations)
  → Answer Collector (8 answers per interpretation)
  → Semantic Clustering (group equivalent answers)
  → Entropy Calculator (compute ambiguity score)
  → Urgency Detector (assign URGENT/SOON/LATER)
  → Store in database
  → Return results
```

**Features:**
- Async processing
- Batch support (10 propositions at a time)
- Progress tracking
- Error recovery
- Database persistence

### 8. API Endpoints
**Next Step**: Extend `dashboard/api_server.py`

**New Endpoints:**
```python
POST   /api/propositions/{id}/analyze-ambiguity
GET    /api/propositions/{id}/ambiguity
GET    /api/propositions/urgent
GET    /api/propositions/ambiguous
POST   /api/propositions/batch-analyze
```

### 9. GATE Question Generator
**Next Step**: Create `gum/gate/question_generator.py`

**Question Types:**
- Multiple choice (present interpretations as options)
- Yes/No (for binary disambiguations)
- Free text (for open-ended clarifications)

**Example:**
```
We've inferred that you prefer Python for development, but we're not 
entirely sure which aspect this refers to:

A) You use Python as your main programming language
B) You prefer Python specifically for data analysis
C) You're currently learning Python
D) Something else (please explain)

Which interpretation best matches your actual behavior?
```

### 10. Frontend UI Components
**Next Step**: Create React components in `dashboard/`

**Components:**
- `AmbiguityBadge`: Visual indicator (color-coded by entropy)
- `UrgencyTag`: URGENT/SOON/LATER badge with tooltip
- `InterpretationsPanel`: Expandable list of alternative meanings
- `ClarificationDialog`: Modal for GATE questions
- `AmbiguityDashboard`: Overview of ambiguous propositions

---

## 📊 Testing & Validation Plan

### 11. Real Data Testing (20 propositions)
- Random sampling from GUM database
- Manual quality assessment
- Interpretation diversity check
- Adjust prompts if needed

### 12. End-to-End Pipeline Testing (10 propositions)
- Full pipeline run
- Validate each stage output
- Check database persistence
- Verify entropy calculations

### 13. Threshold Calibration (50+ labeled propositions)
- Manual labeling (ambiguous vs. clear)
- Grid search for optimal threshold
- Precision/recall analysis
- Document final thresholds

### 14. Comprehensive Test Suite
- Unit tests (each module)
- Integration tests (pipeline)
- API tests (endpoints)
- Database tests (integrity)
- Target: >80% coverage

### 15. Demo & Documentation
- Demo script with examples
- Architecture documentation
- API reference
- Calibration methodology
- Example outputs for paper/poster

---

## 🎯 Publication Readiness

### Target Venues
- CHI Late-Breaking Work (poster/extended abstract)
- UIST Demos/Posters
- NeurIPS/EMNLP Workshops on human-AI interaction

### Key Contributions
1. **Novel Application**: First to apply entropy-based ambiguity detection to passively observed user behavior propositions
2. **Grounded Approach**: Uses actual observations as context (not just isolated text)
3. **Urgency-Aware**: Time-sensitive clarification prioritization
4. **End-to-End System**: Complete pipeline from observation → ambiguity detection → GATE dialogue

### Estimated Timeline
- **Remaining Implementation**: 3-4 weeks
- **Testing & Calibration**: 1-2 weeks
- **Documentation & Demo**: 1 week
- **Total to Submission**: 6-8 weeks

---

## 💡 Key Design Decisions

### 1. Why Entropy-Based Detection?
- Validated by UCSB on AmbiEnt dataset
- Mathematical grounding (not heuristics)
- Interpretable scores
- Threshold calibration possible

### 2. Why Multi-Interpretation Approach?
- Captures semantic ambiguity explicitly
- Provides context for GATE questions
- More robust than single-pass classification
- Enables explanation to users

### 3. Why Urgency Assessment?
- Prevents notification fatigue
- Prioritizes time-sensitive clarifications
- Balances accuracy vs. interruption cost
- Aligns with mixed-initiative interaction principles

### 4. Why Not Train a Model?
- Limited labeled data available
- Pre-trained LLMs already strong
- Faster iteration with prompts
- More transparent/debuggable

---

## 📈 Success Metrics

### Technical Metrics
- **Interpretation Quality**: >85% judged as "distinct" (manual review)
- **Clustering Coherence**: Silhouette score >0.5
- **Ambiguity Detection**: Precision >0.7, Recall >0.6 (vs. manual labels)
- **Urgency Accuracy**: >75% agreement with human judges

### User-Facing Metrics (Future Work)
- GATE dialogue completion rate
- User satisfaction with clarifications
- Improved proposition confidence after clarification
- Reduced false positive actions

---

## 🔧 Development Environment

### Prerequisites
```bash
# Virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .
pip install sentence-transformers hdbscan umap-learn

# Environment variables
export OPENAI_API_KEY="your-key-here"

# Database migration
python gum/migrate_ambiguity_tables.py
```

### Running Tests
```bash
# Interpretation generator test
python test_interpretation_module.py

# Full pipeline test (once implemented)
python test_ambiguity_pipeline.py

# API tests
pytest tests/test_api_ambiguity.py
```

---

## 📝 Next Immediate Steps

1. **Answer Collector** (1-2 days)
   - Implement `answer_collector.py`
   - Test on sample interpretations
   - Validate answer diversity

2. **Clustering** (1-2 days)
   - Implement `clustering.py`
   - Test on sample answers
   - Tune clustering parameters

3. **Entropy Calculator** (1 day)
   - Implement `entropy_calculator.py`
   - Validate math against known examples
   - Test threshold sensitivity

4. **Urgency Detector** (1 day)
   - Implement `urgency_detector.py`
   - Test heuristics on diverse propositions
   - Adjust weights

5. **Pipeline Integration** (2-3 days)
   - Implement `pipeline.py`
   - End-to-end testing
   - Database integration
   - Error handling

After these 5 steps, we'll have a **working prototype** ready for initial validation!

---

## 🎉 Current Status

**Completion: ~15% (2/15 major tasks)**

**What's Working:**
- ✅ Database schema fully designed and migrated
- ✅ Interpretation generation producing high-quality results
- ✅ Configuration system in place
- ✅ Test infrastructure established

**What's Next:**
- Answer collection (critical path)
- Clustering (critical path)
- Entropy calculation (critical path)
- Complete pipeline integration

**Risk Assessment:**
- **Low Risk**: Core infrastructure is solid
- **Medium Risk**: Threshold calibration (needs labeled data)
- **Low Risk**: Module implementation (well-scoped, tested approach)

---

## 📚 References

- UCSB NLP Group: "Detecting and Measuring Ambiguity in Natural Language Inference"
- AmbiEnt Dataset: Benchmark for ambiguity detection
- GUM Framework: Grounded user modeling from observations
- GATE Principles: Adaptive transparent elicitation

---

*Last Updated: 2025-10-05*
*Project: GUM Ambiguity Detection for GATE Integration*
*Developer: Arnav Sharma + AI Assistant*
