#!/usr/bin/env python3
"""
REAL smoke test for the question engine.
This actually runs the code to find what's broken.
"""

import sys
import os
import json
import asyncio

# Add project to path
sys.path.insert(0, '/Users/arnavsharma/.cursor/worktrees/gum-elicitation/moVjG')

print("=" * 80)
print("STEP 1: Test imports")
print("=" * 80)

try:
    from gum.clarification.question_config import get_factor_name, get_method_for_factor
    print("✓ question_config imports successfully")
    print(f"  Factor 1 name: {get_factor_name(1)}")
    print(f"  Factor 1 method: {get_method_for_factor(1)}")
except Exception as e:
    print(f"✗ question_config import failed: {e}")
    sys.exit(1)

try:
    from gum.clarification.question_prompts import build_controlled_qg_prompt
    print("✓ question_prompts imports successfully")
except Exception as e:
    print(f"✗ question_prompts import failed: {e}")
    sys.exit(1)

try:
    from gum.clarification.question_validator import QuestionValidator
    print("✓ question_validator imports successfully")
    validator = QuestionValidator()
    is_valid, errors = validator.validate_question("Could you clarify what you meant?")
    print(f"  Sample validation: valid={is_valid}, errors={errors}")
except Exception as e:
    print(f"✗ question_validator import failed: {e}")
    sys.exit(1)

try:
    from gum.clarification.question_loader import load_flagged_propositions
    print("✓ question_loader imports successfully")
except Exception as e:
    print(f"✗ question_loader import failed: {e}")
    sys.exit(1)

print("\n" + "=" * 80)
print("STEP 2: Load real propositions")
print("=" * 80)

async def test_load_real_propositions():
    try:
        props = await load_flagged_propositions(
            source="file",
            file_path="test_results_200_props/flagged_propositions.json"
        )
        print(f"✓ Loaded {len(props)} propositions")
        if len(props) > 0:
            print(f"  First prop ID: {props[0]['prop_id']}")
            print(f"  First prop text: {props[0]['prop_text'][:100]}...")
            print(f"  Triggered factors: {props[0].get('triggered_factors', [])}")
            print(f"  Observations: {len(props[0].get('observations', []))} observations")
        return props
    except Exception as e:
        print(f"✗ Failed to load propositions: {e}")
        import traceback
        traceback.print_exc()
        return None

props = asyncio.run(test_load_real_propositions())

if not props or len(props) == 0:
    print("Cannot continue without propositions")
    sys.exit(1)

print("\n" + "=" * 80)
print("STEP 3: Test question generation (with mock)")
print("=" * 80)

try:
    from gum.clarification.question_generator import QuestionGenerator
    from unittest.mock import AsyncMock, MagicMock
    
    # Create mock client
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({
        "question": "Could you clarify what you meant by 'actively networking'?",
        "reasoning": "This infers intent from LinkedIn activity; clarifying confirms actual motivation."
    })
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    generator = QuestionGenerator(mock_client, model="gpt-4")
    print("✓ QuestionGenerator created successfully")
    
    # Try to generate a question for the first prop
    async def test_generate():
        prop = props[0]
        factor_name = prop['triggered_factors'][0] if prop['triggered_factors'] else None
        if not factor_name:
            print("✗ First prop has no triggered factors")
            return None
        
        from gum.clarification.question_config import get_factor_id_from_name
        factor_id = get_factor_id_from_name(factor_name)
        if not factor_id:
            print(f"✗ Invalid factor name: {factor_name}")
            return None
        
        print(f"  Generating for prop {prop['prop_id']}, factor {factor_name} (ID: {factor_id})")
        
        try:
            result = await generator.generate_question_pair(
                prop_id=prop['prop_id'],
                prop_text=prop['prop_text'],
                factor_id=factor_id,
                observations=prop.get('observations', []),
                prop_reasoning=prop.get('prop_reasoning')
            )
            print(f"✓ Generated question successfully")
            print(f"  Question: {result['question']}")
            print(f"  Reasoning: {result['reasoning']}")
            print(f"  Evidence: {result['evidence']}")
            return result
        except Exception as e:
            print(f"✗ Generation failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    result = asyncio.run(test_generate())
    
except Exception as e:
    print(f"✗ Failed to test generator: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("STEP 4: Test with REAL OpenAI API (if key available)")
print("=" * 80)

api_key = os.environ.get('OPENAI_API_KEY')
if not api_key:
    print("⚠ OPENAI_API_KEY not set, skipping real API test")
else:
    print(f"✓ API key found (length: {len(api_key)})")
    try:
        from openai import AsyncOpenAI
        
        real_client = AsyncOpenAI(api_key=api_key)
        real_generator = QuestionGenerator(real_client, model="gpt-4")
        
        async def test_real_generation():
            prop = props[0]
            factor_name = prop['triggered_factors'][0] if prop['triggered_factors'] else None
            if not factor_name:
                return None
            
            from gum.clarification.question_config import get_factor_id_from_name
            factor_id = get_factor_id_from_name(factor_name)
            
            print(f"  Making REAL API call for prop {prop['prop_id']}...")
            try:
                result = await real_generator.generate_question_pair(
                    prop_id=prop['prop_id'],
                    prop_text=prop['prop_text'],
                    factor_id=factor_id,
                    observations=[],  # Empty for now since format is unclear
                    prop_reasoning=prop.get('prop_reasoning')
                )
                print(f"✓ REAL API call succeeded!")
                print(f"  Question: {result['question']}")
                print(f"  Reasoning: {result['reasoning']}")
                return result
            except Exception as e:
                print(f"✗ Real API call failed: {e}")
                import traceback
                traceback.print_exc()
                return None
        
        real_result = asyncio.run(test_real_generation())
        
    except Exception as e:
        print(f"✗ Real API test failed: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("If you see this, at least the basic imports work!")
print("Check the output above to see what broke.")

