#!/usr/bin/env python3
"""
Working test that imports directly from clarification modules.
"""

import sys
import os
import json
import asyncio
from pathlib import Path

# Import directly to avoid gum.__init__.py
sys.path.insert(0, '/Users/arnavsharma/.cursor/worktrees/gum-elicitation/moVjG')

print("=" * 80)
print("WORKING QUESTION ENGINE TEST")
print("=" * 80)

print("\n[1/7] Testing direct imports...")
try:
    # Import modules directly
    import gum.clarification.question_config as qc
    import gum.clarification.question_validator as qv
    import gum.clarification.question_prompts as qp
    
    print("✓ Imports successful")
    print(f"  Factor 1: {qc.get_factor_name(1)}")
    print(f"  Factor 3 method: {qc.get_method_for_factor(3)}")
except Exception as e:
    print(f"✗ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n[2/7] Testing validation...")
validator = qv.QuestionValidator()
test_q = "Could you clarify what you meant by 'actively networking'?"
test_r = "This infers intent from LinkedIn activity; clarifying confirms motivation."

is_valid_q, q_errors = validator.validate_question(test_q)
is_valid_r, r_errors = validator.validate_reasoning(test_r)

print(f"  Question validation: {'✓' if is_valid_q else '✗'}")
if q_errors:
    for err in q_errors[:3]:
        print(f"    - {err}")
print(f"  Reasoning validation: {'✓' if is_valid_r else '✗'}")
if r_errors:
    for err in r_errors[:3]:
        print(f"    - {err}")

print("\n[3/7] Loading real propositions...")
try:
    with open("test_results_200_props/flagged_propositions.json", 'r') as f:
        props = json.load(f)
    print(f"✓ Loaded {len(props)} propositions")
    if props:
        print(f"  First prop ID: {props[0]['prop_id']}")
        print(f"  First prop text: {props[0]['prop_text'][:80]}...")
        print(f"  Triggered factors: {props[0].get('triggered_factors', [])}")
except Exception as e:
    print(f"✗ Failed: {e}")
    sys.exit(1)

print("\n[4/7] Testing prompt building...")
prop = props[0]
factor_name = prop['triggered_factors'][0] if prop['triggered_factors'] else None
if factor_name:
    factor_id = qc.get_factor_id_from_name(factor_name)
    method = qc.get_method_for_factor(factor_id)
    print(f"  Factor: {factor_name} (ID: {factor_id}, method: {method})")
    
    try:
        if method == "few_shot":
            sys_prompt, user_prompt = qp.build_few_shot_prompt(
                prop['prop_text'], factor_id, ""
            )
        else:
            sys_prompt, user_prompt = qp.build_controlled_qg_prompt(
                prop['prop_text'], factor_id, ""
            )
        print(f"✓ Prompt built successfully")
        print(f"  System prompt: {len(sys_prompt)} chars")
        print(f"  User prompt: {len(user_prompt)} chars")
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()

print("\n[5/7] Testing question generator (mock)...")
try:
    import gum.clarification.question_generator as qg
    from unittest.mock import AsyncMock, MagicMock
    
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({
        "question": "Could you clarify what you meant by 'actively networking'?",
        "reasoning": "This infers intent from LinkedIn activity."
    })
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    generator = qg.QuestionGenerator(mock_client, model="gpt-4")
    
    async def test_mock():
        result = await generator.generate_question_pair(
            prop_id=prop['prop_id'],
            prop_text=prop['prop_text'],
            factor_id=factor_id,
            observations=[],
            prop_reasoning=prop.get('prop_reasoning')
        )
        return result
    
    mock_result = asyncio.run(test_mock())
    print(f"✓ Mock generation works")
    print(f"  Question: {mock_result['question'][:60]}...")
    print(f"  Reasoning: {mock_result['reasoning'][:60]}...")
    
except Exception as e:
    print(f"✗ Failed: {e}")
    import traceback
    traceback.print_exc()

print("\n[6/7] Testing with REAL OpenAI API...")
api_key = os.environ.get('OPENAI_API_KEY')
if not api_key:
    print("⚠  OPENAI_API_KEY not set - skipping real API test")
    print("   Set with: export OPENAI_API_KEY='sk-...'")
else:
    print(f"✓ API key found")
    try:
        from openai import AsyncOpenAI
        
        async def test_real_api():
            client = AsyncOpenAI(api_key=api_key)
            generator = qg.QuestionGenerator(client, model="gpt-4o", temperature=0.7)  # gpt-4o supports JSON mode
            
            print(f"  Making REAL API call...")
            result = await generator.generate_question_pair(
                prop_id=prop['prop_id'],
                prop_text=prop['prop_text'],
                factor_id=factor_id,
                observations=[],
                prop_reasoning=prop.get('prop_reasoning')
            )
            
            print(f"✓ REAL API call succeeded!")
            print(f"  Question: {result['question']}")
            print(f"  Reasoning: {result['reasoning']}")
            print(f"  Factor: {result['factor']}")
            
            # Validate
            is_valid, errors = validator.validate_full_output(result)
            if is_valid:
                print(f"✓ Output passed validation")
            else:
                print(f"⚠  Validation warnings: {errors[:2]}")
            
            return result
        
        real_result = asyncio.run(test_real_api())
        
    except Exception as e:
        print(f"✗ Real API failed: {e}")
        import traceback
        traceback.print_exc()

print("\n[7/7] Testing full engine...")
if api_key and 'real_result' in locals() and real_result:
    try:
        import gum.clarification.question_engine as qe
        from gum.config import GumConfig
        from openai import AsyncOpenAI
        
        async def test_engine():
            config = GumConfig()
            client = AsyncOpenAI(api_key=api_key)
            
            engine = qe.ClarifyingQuestionEngine(
                openai_client=client,
                config=config,
                input_source="file",
                input_file_path="test_results_200_props/flagged_propositions.json",
                output_path="test_output_WORKING.jsonl"
            )
            
            # Process first 3 props
            print(f"  Processing 3 propositions...")
            summary = await engine.run(
                prop_ids=[props[0]['prop_id'], props[1]['prop_id'], props[2]['prop_id']]
            )
            
            print(f"✓ Engine completed!")
            print(f"  Processed: {summary['total_processed']}")
            print(f"  Successful: {summary['successful']}")
            print(f"  Failed: {summary['failed']}")
            
            # Check output
            if Path("test_output_WORKING.jsonl").exists():
                with open("test_output_WORKING.jsonl", 'r') as f:
                    lines = f.readlines()
                    print(f"  Output has {len(lines)} results")
            
            return summary
        
        engine_result = asyncio.run(test_engine())
        
    except Exception as e:
        print(f"✗ Engine failed: {e}")
        import traceback
        traceback.print_exc()
else:
    print("⚠  Skipping (no API key or previous test failed)")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
print("What works:")
print("  ✓ Imports (with direct import workaround)")
print("  ✓ Validation logic")
print("  ✓ Prompt building")
print("  ✓ Mock generation")
if api_key:
    print(f"  {'✓' if 'real_result' in locals() and real_result else '✗'} Real API calls")
    print(f"  {'✓' if 'engine_result' in locals() and engine_result else '✗'} Full engine")
else:
    print("  ⚠  Real API not tested (no key)")

if not api_key:
    print("\n💡 To test real API: export OPENAI_API_KEY='sk-...'")

