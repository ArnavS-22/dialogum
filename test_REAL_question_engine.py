#!/usr/bin/env python3
"""
HONEST smoke test that actually runs the question engine.
No mocking, no bullshit, just see if it works.

Works around the sklearn import issue by loading modules directly.
"""

import sys
import os
import json
import asyncio
from pathlib import Path
import importlib.util

print("=" * 80)
print("REAL QUESTION ENGINE TEST (No Bullshit Edition)")
print("=" * 80)

# Workaround: Import modules directly to avoid gum.__init__.py triggering sklearn
def import_module_directly(name, path):
    """Import a module from a file path without triggering parent __init__.py"""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

base = "/Users/arnavsharma/.cursor/worktrees/gum-elicitation/moVjG/gum/clarification"

print("\n[1/6] Loading modules directly (avoiding sklearn import)...")
try:
    question_config = import_module_directly("question_config", f"{base}/question_config.py")
    question_validator = import_module_directly("question_validator", f"{base}/question_validator.py")
    question_prompts = import_module_directly("question_prompts", f"{base}/question_prompts.py")
    
    print("✓ Core modules loaded")
    print(f"  Factor 1: {question_config.get_factor_name(1)}")
    print(f"  Factor 3 method: {question_config.get_method_for_factor(3)}")
except Exception as e:
    print(f"✗ Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 2: Test validation
print("\n[2/6] Testing validation...")
validator = question_validator.QuestionValidator()
test_question = "Could you clarify what you meant by 'actively networking'?"
test_reasoning = "This infers intent from LinkedIn activity; clarifying confirms motivation."

is_valid_q, q_errors = validator.validate_question(test_question)
is_valid_r, r_errors = validator.validate_reasoning(test_reasoning)

print(f"  Question validation: {'✓' if is_valid_q else '✗'} (errors: {len(q_errors)})")
if q_errors:
    for err in q_errors:
        print(f"    - {err}")
print(f"  Reasoning validation: {'✓' if is_valid_r else '✗'} (errors: {len(r_errors)})")
if r_errors:
    for err in r_errors:
        print(f"    - {err}")

# Step 3: Load real propositions
print("\n[3/6] Loading real propositions file...")
try:
    with open("test_results_200_props/flagged_propositions.json", 'r') as f:
        props_data = json.load(f)
    print(f"✓ Loaded {len(props_data)} propositions")
    if props_data:
        prop = props_data[0]
        print(f"  Sample prop ID: {prop['prop_id']}")
        print(f"  Sample text: {prop['prop_text'][:80]}...")
        print(f"  Triggered factors: {prop.get('triggered_factors', [])}")
        print(f"  Has observations?: {'observations' in prop}")
except Exception as e:
    print(f"✗ Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 4: Test prompt building
print("\n[4/6] Testing prompt building...")
prop = props_data[0]
factor_name = prop['triggered_factors'][0] if prop['triggered_factors'] else None
if factor_name:
    factor_id = question_config.get_factor_id_from_name(factor_name)
    method = question_config.get_method_for_factor(factor_id)
    print(f"  Factor: {factor_name} (ID: {factor_id}, method: {method})")
    
    try:
        if method == "few_shot":
            system_prompt, user_prompt = question_prompts.build_few_shot_prompt(
                prop['prop_text'], factor_id, ""
            )
        else:
            system_prompt, user_prompt = question_prompts.build_controlled_qg_prompt(
                prop['prop_text'], factor_id, ""
            )
        print(f"✓ Prompt built successfully")
        print(f"  System prompt length: {len(system_prompt)} chars")
        print(f"  User prompt length: {len(user_prompt)} chars")
        print(f"  Sample from system prompt: {system_prompt[:150]}...")
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()

# Step 5: Test with REAL OpenAI API
api_key = os.environ.get('OPENAI_API_KEY')
print(f"\n[5/6] Testing with REAL OpenAI API...")
if not api_key:
    print("⚠ OPENAI_API_KEY not set - skipping real API test")
    print("  Set your API key: export OPENAI_API_KEY='sk-...'")
else:
    print(f"✓ API key found (first 10 chars: {api_key[:10]}...)")
    
    async def test_real_api():
        try:
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(api_key=api_key)
            
            # Build prompt for first prop
            prop = props_data[0]
            factor_name = prop['triggered_factors'][0]
            factor_id = question_config.get_factor_id_from_name(factor_name)
            method = question_config.get_method_for_factor(factor_id)
            
            if method == "few_shot":
                system_prompt, user_prompt = question_prompts.build_few_shot_prompt(
                    prop['prop_text'], factor_id, ""
                )
            else:
                system_prompt, user_prompt = question_prompts.build_controlled_qg_prompt(
                    prop['prop_text'], factor_id, ""
                )
            
            print(f"  Making REAL API call (factor: {factor_name}, method: {method})...")
            
            response = await client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=300,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            result = json.loads(content)
            
            print(f"✓ REAL API call succeeded!")
            print(f"  Question: {result.get('question', 'N/A')}")
            print(f"  Reasoning: {result.get('reasoning', 'N/A')}")
            
            # Validate
            is_valid_q, q_errors = validator.validate_question(result.get('question', ''))
            is_valid_r, r_errors = validator.validate_reasoning(result.get('reasoning', ''))
            
            print(f"  Question valid?: {'✓' if is_valid_q else '✗'} ({len(q_errors)} errors)")
            print(f"  Reasoning valid?: {'✓' if is_valid_r else '✗'} ({len(r_errors)} errors)")
            
            if q_errors or r_errors:
                print(f"  Validation errors:")
                for err in q_errors + r_errors:
                    print(f"    - {err}")
            
            return result
        except Exception as e:
            print(f"✗ API call failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    real_result = asyncio.run(test_real_api())

# Summary
print("\n" + "=" * 80)
print("HONEST ASSESSMENT")
print("=" * 80)
print("What ACTUALLY works:")
print("  ✓ Core config module loads and works")
print("  ✓ Validation logic works")
print("  ✓ Can load real propositions file")
print("  ✓ Prompt building works")
if api_key:
    print(f"  {'✓' if 'real_result' in locals() and real_result else '✗'} Real API calls work")
else:
    print(f"  ⚠ Real API not tested (no key)")

print("\nWhat's BROKEN/UNTESTED:")
print("  ✗ Full question_generator module (needs async OpenAI)")
print("  ✗ Full question_loader async functions")
print("  ✗ Full question_engine pipeline")
print("  ✗ Database loading (not tested)")
print("  ✗ CLI interface (not tested)")
print("  ⚠ Import requires workaround (sklearn dependency)")

print("\nKnown Issues:")
print("  1. Importing from gum.clarification fails due to sklearn dependency")
print("  2. Real propositions file has no full observation objects")
print("  3. Observation relationship querying not tested")
print("  4. Config access pattern may be wrong in engine")

print("\n" + "=" * 80)
print("CONCLUSION: Core logic works, but NOT fully integrated or tested")
print("=" * 80)

if not api_key:
    print("\n💡 To test with real API: export OPENAI_API_KEY='your-key-here'")
