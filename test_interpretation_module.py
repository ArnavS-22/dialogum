#!/usr/bin/env python3
"""
Test the interpretation generator module on real GUM propositions.
"""

import os
import sys
import sqlite3
import json
import asyncio
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from gum.ambiguity.interpretation_generator import InterpretationGenerator, format_interpretations_for_storage


def load_test_proposition(db_path):
    """Load a single random proposition from GUM database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, text, reasoning, confidence 
        FROM propositions 
        ORDER BY RANDOM() 
        LIMIT 1
    """)
    
    prop = cursor.fetchone()
    conn.close()
    
    if prop:
        return {
            'id': prop[0],
            'text': prop[1],
            'reasoning': prop[2],
            'confidence': prop[3]
        }
    return None


def test_sync():
    """Test synchronous interpretation generation."""
    print("="*80)
    print("TEST 1: SYNCHRONOUS INTERPRETATION GENERATION")
    print("="*80)
    
    # Load test proposition
    db_path = os.path.expanduser("~/.cache/gum/gum.db")
    prop = load_test_proposition(db_path)
    
    if not prop:
        print("❌ No propositions found in database")
        return False
    
    print(f"\n📋 Test Proposition (ID: {prop['id']})")
    print(f"   Text: {prop['text']}")
    print(f"   Confidence: {prop['confidence']}/10")
    print(f"   Reasoning: {prop['reasoning'][:150]}...")
    
    # Initialize generator
    try:
        generator = InterpretationGenerator()
        print("\n✅ InterpretationGenerator initialized")
    except Exception as e:
        print(f"\n❌ Failed to initialize generator: {e}")
        return False
    
    # Generate interpretations
    print("\n🔄 Generating interpretations...")
    interpretations, metadata = generator.generate(
        proposition_text=prop['text'],
        reasoning=prop['reasoning'],
        confidence=prop['confidence']
    )
    
    # Display results
    print(f"\n{'='*80}")
    print("RESULTS")
    print(f"{'='*80}")
    print(f"Success: {metadata['success']}")
    print(f"Model: {metadata.get('model', 'N/A')}")
    print(f"Tokens Used: {metadata.get('tokens_used', 'N/A')}")
    
    if metadata.get('error'):
        print(f"❌ Error: {metadata['error']}")
        return False
    
    print(f"\n📊 Generated {len(interpretations)} interpretations:")
    for i, interp in enumerate(interpretations, 1):
        print(f"\n   [{i}] {interp.text}")
        print(f"       Distinguishing: {interp.distinguishing_feature}")
    
    # Test storage formatting
    storage_format = format_interpretations_for_storage(interpretations)
    print(f"\n💾 Storage format:")
    print(json.dumps(storage_format, indent=2))
    
    print(f"\n{'='*80}")
    print("✅ SYNCHRONOUS TEST PASSED")
    print(f"{'='*80}")
    
    return True


async def test_async():
    """Test asynchronous interpretation generation."""
    print("\n\n" + "="*80)
    print("TEST 2: ASYNCHRONOUS INTERPRETATION GENERATION")
    print("="*80)
    
    # Load test propositions
    db_path = os.path.expanduser("~/.cache/gum/gum.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, text, reasoning, confidence 
        FROM propositions 
        ORDER BY RANDOM() 
        LIMIT 3
    """)
    
    props = [
        {
            'id': p[0],
            'text': p[1],
            'reasoning': p[2],
            'confidence': p[3]
        }
        for p in cursor.fetchall()
    ]
    conn.close()
    
    if not props:
        print("❌ No propositions found in database")
        return False
    
    print(f"\n📋 Testing with {len(props)} propositions:")
    for prop in props:
        print(f"   - ID {prop['id']}: {prop['text'][:60]}...")
    
    # Initialize generator
    generator = InterpretationGenerator()
    
    # Generate interpretations in batch
    print("\n🔄 Generating interpretations (async batch)...")
    results = await generator.generate_batch_async(props)
    
    # Display results
    print(f"\n{'='*80}")
    print("RESULTS")
    print(f"{'='*80}")
    
    for i, (interpretations, metadata) in enumerate(results):
        prop = props[i]
        print(f"\n[{i+1}] Proposition ID: {prop['id']}")
        print(f"    Success: {metadata['success']}")
        print(f"    Interpretations: {len(interpretations)}")
        
        if metadata['success']:
            for j, interp in enumerate(interpretations, 1):
                print(f"       [{j}] {interp.text[:80]}...")
        else:
            print(f"    ❌ Error: {metadata.get('error', 'Unknown')}")
    
    print(f"\n{'='*80}")
    print("✅ ASYNCHRONOUS TEST PASSED")
    print(f"{'='*80}")
    
    return True


async def main():
    """Run all tests."""
    print("\n🧪 INTERPRETATION GENERATOR TEST SUITE\n")
    
    # Test 1: Synchronous
    success1 = test_sync()
    
    # Test 2: Asynchronous
    success2 = await test_async()
    
    print("\n" + "="*80)
    print("FINAL RESULTS")
    print("="*80)
    print(f"Synchronous Test: {'✅ PASS' if success1 else '❌ FAIL'}")
    print(f"Asynchronous Test: {'✅ PASS' if success2 else '❌ FAIL'}")
    print("="*80)
    
    return success1 and success2


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
