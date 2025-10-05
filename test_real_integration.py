#!/usr/bin/env python3
"""
REAL END-TO-END INTEGRATION TEST
Tests the full pipeline with actual database persistence.
This is what actually proves the system works.
"""

import os
import sys
import asyncio
import sqlite3
from pathlib import Path
from datetime import datetime
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from gum.models import init_db
from gum.ambiguity_models import AmbiguityAnalysis, UrgencyAssessment
from gum.ambiguity.interpretation_generator import InterpretationGenerator, format_interpretations_for_storage
from gum.ambiguity.answer_collector import AnswerCollector, format_answers_for_storage, get_answer_texts
from gum.ambiguity.clustering import SemanticClusterer, format_clusters_for_storage
from gum.ambiguity.entropy_calculator import EntropyCalculator, format_entropy_for_storage

from sqlalchemy import select


async def test_full_pipeline_with_db():
    """Test the complete pipeline with database persistence."""
    
    print("="*80)
    print("REAL END-TO-END INTEGRATION TEST")
    print("="*80)
    
    # Connect to GUM database
    db_path = os.path.expanduser("~/.cache/gum/gum.db")
    print(f"\n📁 Connecting to: {db_path}")
    
    engine, Session = await init_db(db_path)
    
    # 1. Load a real proposition
    print("\n[1/7] Loading real proposition from GUM database...")
    async with Session() as session:
        result = await session.execute(
            select(models.Proposition)
            .order_by(models.Proposition.created_at.desc())
            .limit(1)
        )
        proposition = result.scalar_one()
        
        print(f"   ✓ Loaded proposition #{proposition.id}")
        print(f"     Text: {proposition.text[:80]}...")
        print(f"     Confidence: {proposition.confidence}/10")
    
    # 2. Generate interpretations
    print("\n[2/7] Generating interpretations...")
    generator = InterpretationGenerator()
    interpretations, gen_metadata = await generator.generate_async(
        proposition_text=proposition.text,
        reasoning=proposition.reasoning,
        confidence=proposition.confidence
    )
    
    if not gen_metadata['success']:
        print(f"   ✗ Failed: {gen_metadata['error']}")
        return False
    
    print(f"   ✓ Generated {len(interpretations)} interpretations")
    print(f"     Tokens used: {gen_metadata['tokens_used']}")
    
    # 3. Collect answers
    print("\n[3/7] Collecting answers (5 per interpretation)...")
    collector = AnswerCollector()
    answers, ans_metadata = await collector.collect_answers_async(
        interpretations=interpretations,
        proposition_text=proposition.text,
        reasoning=proposition.reasoning,
        num_answers_per_interpretation=5
    )
    
    if not ans_metadata['success']:
        print(f"   ✗ Failed: {ans_metadata['error']}")
        return False
    
    print(f"   ✓ Collected {ans_metadata['successful_answers']} answers")
    print(f"     Failed: {ans_metadata['failed_answers']}")
    print(f"     Total tokens: {ans_metadata['total_tokens_used']}")
    
    # 4. Cluster answers
    print("\n[4/7] Clustering answers semantically...")
    answer_texts = get_answer_texts(answers)
    
    if len(answer_texts) < 2:
        print(f"   ✗ Not enough valid answers: {len(answer_texts)}")
        return False
    
    clusterer = SemanticClusterer()
    cluster_result = clusterer.cluster(answer_texts)
    
    print(f"   ✓ Found {cluster_result.num_clusters} clusters")
    print(f"     Method: {cluster_result.method}")
    print(f"     Silhouette: {cluster_result.silhouette:.3f}" if cluster_result.silhouette else "     Silhouette: N/A")
    print(f"     Cluster sizes: {cluster_result.cluster_sizes}")
    
    # 5. Calculate entropy
    print("\n[5/7] Calculating entropy...")
    entropy_calc = EntropyCalculator()
    entropy_result = entropy_calc.calculate(cluster_result)
    
    print(f"   ✓ Entropy: {entropy_result.entropy_score:.3f} bits")
    print(f"     Normalized: {entropy_result.normalized_entropy:.3f}")
    print(f"     Ambiguous: {entropy_result.is_ambiguous}")
    print(f"     Threshold: {entropy_result.threshold_used}")
    
    # 6. SAVE TO DATABASE
    print("\n[6/7] Saving to database...")
    
    try:
        async with Session() as session:
            # Create AmbiguityAnalysis record
            analysis = AmbiguityAnalysis(
                proposition_id=proposition.id,
                interpretations=format_interpretations_for_storage(interpretations),
                num_interpretations=len(interpretations),
                answers=format_answers_for_storage(answers),
                clusters=format_clusters_for_storage(cluster_result, answer_texts),
                num_clusters=cluster_result.num_clusters,
                entropy_score=entropy_result.entropy_score,
                is_ambiguous=entropy_result.is_ambiguous,
                threshold_used=entropy_result.threshold_used,
                model_used=gen_metadata['model'],
                config={
                    "generation": {
                        "temperature": gen_metadata['temperature'],
                        "tokens": gen_metadata['tokens_used']
                    },
                    "collection": {
                        "num_answers": ans_metadata['answers_per_interpretation'],
                        "tokens": ans_metadata['total_tokens_used']
                    },
                    "clustering": {
                        "method": cluster_result.method,
                        "silhouette": cluster_result.silhouette
                    }
                }
            )
            
            session.add(analysis)
            await session.commit()
            await session.refresh(analysis)
            
            analysis_id = analysis.id
            
            print(f"   ✓ Saved AmbiguityAnalysis #{analysis_id}")
    
    except Exception as e:
        print(f"   ✗ Database save failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 7. READ IT BACK
    print("\n[7/7] Reading back from database...")
    
    try:
        async with Session() as session:
            result = await session.execute(
                select(AmbiguityAnalysis)
                .where(AmbiguityAnalysis.id == analysis_id)
            )
            retrieved = result.scalar_one()
            
            print(f"   ✓ Retrieved AmbiguityAnalysis #{retrieved.id}")
            print(f"     Proposition ID: {retrieved.proposition_id}")
            print(f"     Entropy: {retrieved.entropy_score:.3f}")
            print(f"     Ambiguous: {retrieved.is_ambiguous}")
            print(f"     Interpretations: {retrieved.num_interpretations}")
            print(f"     Clusters: {retrieved.num_clusters}")
            print(f"     Created: {retrieved.created_at}")
            
            # Verify JSON fields are intact
            assert retrieved.num_interpretations == len(interpretations)
            assert retrieved.entropy_score == entropy_result.entropy_score
            assert 'interpretations' in retrieved.interpretations
            assert 'clusters' in retrieved.clusters
            
            print(f"   ✓ JSON fields intact")
    
    except Exception as e:
        print(f"   ✗ Database read failed: {e}")
        return False
    
    # Cleanup (optional - leave data for inspection)
    # await session.delete(retrieved)
    # await session.commit()
    
    await engine.dispose()
    
    print("\n" + "="*80)
    print("✅ FULL INTEGRATION TEST PASSED")
    print("="*80)
    print(f"\nResults saved to database:")
    print(f"  AmbiguityAnalysis ID: {analysis_id}")
    print(f"  Proposition ID: {proposition.id}")
    print(f"  Entropy: {entropy_result.entropy_score:.3f} bits")
    print(f"  Ambiguous: {entropy_result.is_ambiguous}")
    print(f"\nYou can inspect with:")
    print(f"  sqlite3 {db_path}")
    print(f"  SELECT * FROM ambiguity_analyses WHERE id={analysis_id};")
    print("="*80)
    
    return True


async def test_entropy_math():
    """Test entropy calculation with known distributions."""
    
    print("\n" + "="*80)
    print("ENTROPY MATH VALIDATION")
    print("="*80)
    
    calc = EntropyCalculator()
    
    test_cases = [
        {
            "name": "Unambiguous (all in one cluster)",
            "dist": np.array([1.0]),
            "expected_entropy": 0.0,
            "expected_ambiguous": False
        },
        {
            "name": "Two equal clusters (max ambiguity for 2)",
            "dist": np.array([0.5, 0.5]),
            "expected_entropy": 1.0,
            "expected_ambiguous": True
        },
        {
            "name": "Three equal clusters (max ambiguity for 3)",
            "dist": np.array([1/3, 1/3, 1/3]),
            "expected_entropy": 1.585,  # log2(3)
            "expected_ambiguous": True
        },
        {
            "name": "Skewed distribution (low ambiguity)",
            "dist": np.array([0.8, 0.1, 0.1]),
            "expected_entropy": 0.92,
            "expected_ambiguous": True  # Just above threshold
        },
        {
            "name": "Very skewed (near unambiguous)",
            "dist": np.array([0.95, 0.05]),
            "expected_entropy": 0.286,
            "expected_ambiguous": False
        }
    ]
    
    all_passed = True
    for i, test in enumerate(test_cases, 1):
        result = calc.calculate_from_distribution(test['dist'])
        
        entropy_matches = abs(result.entropy_score - test['expected_entropy']) < 0.01
        ambiguous_matches = result.is_ambiguous == test['expected_ambiguous']
        
        status = "✓" if (entropy_matches and ambiguous_matches) else "✗"
        print(f"\n  {status} Test {i}: {test['name']}")
        print(f"     Expected entropy: {test['expected_entropy']:.3f}")
        print(f"     Actual entropy: {result.entropy_score:.3f}")
        print(f"     Expected ambiguous: {test['expected_ambiguous']}")
        print(f"     Actual ambiguous: {result.is_ambiguous}")
        
        if not (entropy_matches and ambiguous_matches):
            all_passed = False
    
    print("\n" + "="*80)
    if all_passed:
        print("✅ ENTROPY MATH VALIDATION PASSED")
    else:
        print("✗ ENTROPY MATH VALIDATION FAILED")
    print("="*80)
    
    return all_passed


async def main():
    """Run all tests."""
    print("\n🔬 REAL INTEGRATION TEST SUITE\n")
    
    # Test 1: Entropy math
    math_ok = await test_entropy_math()
    
    # Test 2: Full pipeline
    if math_ok:
        pipeline_ok = await test_full_pipeline_with_db()
    else:
        print("\n⚠️  Skipping pipeline test due to math failures")
        pipeline_ok = False
    
    print("\n" + "="*80)
    print("FINAL RESULTS")
    print("="*80)
    print(f"Entropy Math: {'✅ PASS' if math_ok else '❌ FAIL'}")
    print(f"Full Pipeline: {'✅ PASS' if pipeline_ok else '❌ FAIL'}")
    print("="*80)
    
    return math_ok and pipeline_ok


if __name__ == "__main__":
    # Import models module
    from gum import models
    
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
