#!/usr/bin/env python3
"""
Test interpretation generation on real GUM propositions.
This validates whether UCSB's approach works for user behavior propositions.
"""

import os
import sqlite3
import json
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# System prompt adapted from UCSB
SYSTEM_PROMPT = """You are analyzing propositions about user behavior that were inferred from observations.
These propositions may be ambiguous - they could mean different things.

Your job: Generate 2-4 DISTINCT interpretations of what the proposition could mean.

Each interpretation must:
1. Be a specific, concrete statement (not vague)
2. Be meaningfully different from other interpretations (not just reworded)
3. Explain what makes this interpretation distinct

Common sources of ambiguity in user behavior:
- Scope: narrow vs broad (e.g., "uses Python" = for specific tasks vs generally)
- Context: what situation (e.g., "reads articles" = for work vs leisure vs learning)
- Temporal: currently vs historically vs planning to
- Intensity: strong preference vs casual interest vs exploratory
- Purpose: doing for work vs personal interest vs learning

Format your response EXACTLY as:
Interpretation 1: [specific statement]
Distinguishing feature: [what makes this different]

Interpretation 2: [specific statement]
Distinguishing feature: [what makes this different]

Interpretation 3: [specific statement]
Distinguishing feature: [what makes this different]

If the proposition is already completely clear and unambiguous, output:
"No ambiguity detected - single clear interpretation"
"""

def generate_interpretations(proposition_text, reasoning, confidence):
    """Generate interpretations for a single proposition."""
    
    user_prompt = f"""Proposition: "{proposition_text}"

How this was inferred: "{reasoning}"

GUM's confidence: {confidence}/10

Generate 2-4 distinct interpretations of what this proposition could mean."""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=1.0,  # High temp for diversity
            max_tokens=500
        )
        
        return response.choices[0].message.content
    except Exception as e:
        return f"ERROR: {str(e)}"

def load_test_propositions(db_path, limit=10):
    """Load random propositions from GUM database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, text, reasoning, confidence 
        FROM propositions 
        ORDER BY RANDOM() 
        LIMIT ?
    """, (limit,))
    
    props = cursor.fetchall()
    conn.close()
    
    return [
        {
            'id': p[0],
            'text': p[1],
            'reasoning': p[2],
            'confidence': p[3]
        }
        for p in props
    ]

def evaluate_quality(interpretations_text):
    """Manual quality assessment helper."""
    print("\n" + "="*80)
    print("QUALITY ASSESSMENT")
    print("="*80)
    print("\nAre the interpretations:")
    print("1. Meaningfully distinct (not just reworded)? [Y/N]")
    print("2. Plausible given the evidence? [Y/N]")
    print("3. Specific and concrete (not vague)? [Y/N]")
    print("\nRate overall quality: [GOOD/OK/BAD]")
    print("="*80)

def main():
    # Load test propositions
    db_path = os.path.expanduser("~/.cache/gum/gum.db")
    propositions = load_test_propositions(db_path, limit=10)
    
    print(f"Loaded {len(propositions)} test propositions\n")
    print("="*80)
    print("INTERPRETATION GENERATION TEST")
    print("="*80)
    
    results = []
    
    for i, prop in enumerate(propositions, 1):
        print(f"\n\n{'='*80}")
        print(f"TEST {i}/10")
        print(f"{'='*80}")
        print(f"\nProposition ID: {prop['id']}")
        print(f"Confidence: {prop['confidence']}/10")
        print(f"\nText: {prop['text']}")
        print(f"\nReasoning: {prop['reasoning'][:200]}...")
        
        print(f"\n{'-'*80}")
        print("GENERATING INTERPRETATIONS...")
        print(f"{'-'*80}")
        
        interpretations = generate_interpretations(
            prop['text'],
            prop['reasoning'],
            prop['confidence']
        )
        
        print(f"\n{interpretations}")
        
        evaluate_quality(interpretations)
        
        results.append({
            'proposition': prop,
            'interpretations': interpretations
        })
        
        # Save intermediate results
        with open('/Users/arnavsharma/gum-elicitation/interpretation_test_results.json', 'w') as f:
            json.dump(results, f, indent=2)
    
    print(f"\n\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}")
    print(f"\nResults saved to: interpretation_test_results.json")
    print("\nManual review needed to assess quality.")
    print("Look for: distinct interpretations, not just rewordings.")

if __name__ == "__main__":
    main()
