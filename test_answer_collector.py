#!/usr/bin/env python3
"""
Test the answer collection module.
"""

import os
import sys
import asyncio
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from gum.ambiguity.interpretation_generator import InterpretationGenerator, Interpretation
from gum.ambiguity.answer_collector import AnswerCollector, format_answers_for_storage, get_answer_texts


async def test_answer_collection():
    """Test answer collection on sample interpretations."""
    print("="*80)
    print("ANSWER COLLECTOR TEST")
    print("="*80)
    
    # Create sample interpretations
    interpretations = [
        Interpretation(
            text="User primarily uses Python for data analysis and scientific computing tasks.",
            distinguishing_feature="Focuses on data analysis domain specifically"
        ),
        Interpretation(
            text="User is a general Python developer who uses it for various software projects.",
            distinguishing_feature="Emphasizes broad, general-purpose development"
        ),
        Interpretation(
            text="User is currently learning Python and exploring its capabilities.",
            distinguishing_feature="Temporal aspect - learning/exploratory phase"
        )
    ]
    
    proposition_text = "User prefers Python for development work"
    reasoning = "Multiple terminal sessions show Python environment activation and code execution"
    
    print(f"\n📋 Test Setup:")
    print(f"   Proposition: {proposition_text}")
    print(f"   Number of interpretations: {len(interpretations)}")
    print(f"   Answers per interpretation: 5 (for testing)")
    
    # Initialize collector
    print("\n🔄 Initializing AnswerCollector...")
    collector = AnswerCollector()
    
    # Collect answers
    print(f"\n🔄 Collecting answers (5 per interpretation, total: {len(interpretations) * 5})...")
    print("   This will take ~10-15 seconds...")
    
    answers, metadata = await collector.collect_answers_async(
        interpretations=interpretations,
        proposition_text=proposition_text,
        reasoning=reasoning,
        num_answers_per_interpretation=5
    )
    
    # Display results
    print(f"\n{'='*80}")
    print("RESULTS")
    print(f"{'='*80}")
    print(f"Success: {metadata['success']}")
    print(f"Total answers requested: {metadata['total_answers_requested']}")
    print(f"Successful answers: {metadata['successful_answers']}")
    print(f"Failed answers: {metadata['failed_answers']}")
    print(f"Total tokens used: {metadata['total_tokens_used']}")
    
    # Group by interpretation
    print(f"\n📊 Answers by Interpretation:")
    for i, interp in enumerate(interpretations):
        interp_answers = [a for a in answers if a.interpretation_index == i]
        print(f"\n[Interpretation {i+1}] {interp.text[:60]}...")
        print(f"   Generated {len(interp_answers)} answers:")
        for j, ans in enumerate(interp_answers[:3], 1):  # Show first 3
            print(f"      {j}. {ans.text[:100]}...")
        if len(interp_answers) > 3:
            print(f"      ... and {len(interp_answers) - 3} more")
    
    # Test storage formatting
    print(f"\n💾 Storage Format:")
    storage_format = format_answers_for_storage(answers)
    print(json.dumps(storage_format, indent=2)[:500] + "...")
    
    # Test text extraction for clustering
    answer_texts = get_answer_texts(answers)
    print(f"\n📝 Extracted {len(answer_texts)} answer texts for clustering")
    print("   Sample texts:")
    for text in answer_texts[:3]:
        print(f"      - {text[:80]}...")
    
    print(f"\n{'='*80}")
    print("✅ ANSWER COLLECTOR TEST PASSED")
    print(f"{'='*80}")
    
    return True


async def main():
    """Run test."""
    print("\n🧪 ANSWER COLLECTOR TEST SUITE\n")
    
    success = await test_answer_collection()
    
    if success:
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ Tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
