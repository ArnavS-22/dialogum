#!/usr/bin/env python3
"""
Test the pipeline on 10+ diverse propositions to validate robustness.
This is the real test - does it work on varied data or just one lucky case?
"""

import os
import sys
import asyncio
import sqlite3
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent))

from gum.models import init_db
from gum import models
from gum.ambiguity.interpretation_generator import InterpretationGenerator, format_interpretations_for_storage
from gum.ambiguity.answer_collector import AnswerCollector, format_answers_for_storage, get_answer_texts
from gum.ambiguity.clustering import SemanticClusterer, format_clusters_for_storage
from gum.ambiguity.entropy_calculator import EntropyCalculator, format_entropy_for_storage, interpret_entropy
from gum.ambiguity.urgency_detector import UrgencyDetector, format_urgency_for_storage
from gum.ambiguity_models import AmbiguityAnalysis, UrgencyAssessment

from sqlalchemy import select
import numpy as np


async def test_multiple_propositions(num_propositions=10):
    """Test pipeline on multiple diverse propositions."""
    
    print("="*80)
    print(f"TESTING PIPELINE ON {num_propositions} DIVERSE PROPOSITIONS")
    print("="*80)
    
    # Connect to database
    db_path = os.path.expanduser("~/.cache/gum/gum.db")
    engine, Session = await init_db(db_path)
    
    # Load diverse propositions (different confidence levels, lengths, topics)
    print(f"\n[1/{num_propositions+2}] Loading {num_propositions} random propositions...")
    async with Session() as session:
        # First, get IDs of already-analyzed propositions
        analyzed_result = await session.execute(
            select(AmbiguityAnalysis.proposition_id)
        )
        analyzed_ids = set(row[0] for row in analyzed_result.all())
        print(f"   Found {len(analyzed_ids)} already-analyzed propositions, skipping those...")
        
        # Get propositions that haven't been analyzed yet
        result = await session.execute(
            select(models.Proposition)
            .where(~models.Proposition.id.in_(analyzed_ids) if analyzed_ids else True)
            .order_by(models.Proposition.id.desc())  # Get recent ones
            .limit(num_propositions * 2)  # Get more to filter
        )
        all_props = result.scalars().all()
        
        # Select diverse set
        propositions = []
        confidence_ranges = {
            'low': (1, 4),
            'medium': (5, 7),
            'high': (8, 10)
        }
        
        for range_name, (min_conf, max_conf) in confidence_ranges.items():
            matching = [p for p in all_props 
                       if p.confidence and min_conf <= p.confidence <= max_conf]
            if matching:
                propositions.extend(matching[:3])  # 3 from each range
        
        # Add one more if we don't have enough
        while len(propositions) < num_propositions and len(propositions) < len(all_props):
            for p in all_props:
                if p not in propositions:
                    propositions.append(p)
                    if len(propositions) >= num_propositions:
                        break
        
        propositions = propositions[:num_propositions]
    
    print(f"   ✓ Loaded {len(propositions)} propositions")
    print(f"   Confidence distribution:")
    for p in propositions:
        print(f"     - ID {p.id}: confidence={p.confidence}/10, len={len(p.text)} chars")
    
    # Initialize all modules
    print(f"\n[2/{num_propositions+2}] Initializing modules...")
    generator = InterpretationGenerator()
    collector = AnswerCollector()
    clusterer = SemanticClusterer()
    entropy_calc = EntropyCalculator()
    urgency_detector = UrgencyDetector()
    print("   ✓ All modules initialized")
    
    # Process each proposition
    results = []
    failures = []
    
    for i, prop in enumerate(propositions, 1):
        print(f"\n{'='*80}")
        print(f"PROPOSITION {i}/{len(propositions)} - ID: {prop.id}")
        print(f"{'='*80}")
        print(f"Text: {prop.text[:100]}...")
        print(f"Confidence: {prop.confidence}/10")
        
        try:
            # Step 1: Generate interpretations
            print(f"\n  [Step 1/6] Generating interpretations...")
            interpretations, gen_meta = await generator.generate_async(
                proposition_text=prop.text,
                reasoning=prop.reasoning,
                confidence=prop.confidence
            )
            
            if not gen_meta['success'] or len(interpretations) == 0:
                print(f"    ✗ Failed to generate interpretations: {gen_meta.get('error', 'No interpretations')}")
                failures.append({
                    'prop_id': prop.id,
                    'stage': 'interpretation',
                    'error': gen_meta.get('error', 'No interpretations')
                })
                continue
            
            print(f"    ✓ Generated {len(interpretations)} interpretations ({gen_meta['tokens_used']} tokens)")
            
            # Step 2: Collect answers
            print(f"  [Step 2/6] Collecting answers...")
            answers, ans_meta = await collector.collect_answers_async(
                interpretations=interpretations,
                proposition_text=prop.text,
                reasoning=prop.reasoning,
                num_answers_per_interpretation=5
            )
            
            if not ans_meta['success'] or ans_meta['successful_answers'] == 0:
                print(f"    ✗ Failed to collect answers")
                failures.append({
                    'prop_id': prop.id,
                    'stage': 'answers',
                    'error': 'No successful answers'
                })
                continue
            
            print(f"    ✓ Collected {ans_meta['successful_answers']} answers ({ans_meta['total_tokens_used']} tokens)")
            
            # Step 3: Cluster
            print(f"  [Step 3/6] Clustering...")
            answer_texts = get_answer_texts(answers)
            
            if len(answer_texts) < 2:
                print(f"    ✗ Not enough valid answers: {len(answer_texts)}")
                failures.append({
                    'prop_id': prop.id,
                    'stage': 'clustering',
                    'error': f'Only {len(answer_texts)} valid answers'
                })
                continue
            
            cluster_result = clusterer.cluster(answer_texts)
            print(f"    ✓ Found {cluster_result.num_clusters} clusters (method: {cluster_result.method})")
            if cluster_result.silhouette:
                print(f"      Silhouette: {cluster_result.silhouette:.3f}")
            
            # Step 4: Calculate entropy
            print(f"  [Step 4/6] Calculating entropy...")
            entropy_result = entropy_calc.calculate(cluster_result)
            print(f"    ✓ Entropy: {entropy_result.entropy_score:.3f} bits")
            print(f"      Ambiguous: {entropy_result.is_ambiguous}")
            print(f"      Interpretation: {interpret_entropy(entropy_result.entropy_score)}")
            
            # Step 5: Assess urgency
            print(f"  [Step 5/6] Assessing urgency...")
            urgency_result = urgency_detector.assess(
                entropy_result=entropy_result,
                proposition_text=prop.text,
                confidence=prop.confidence
            )
            print(f"    ✓ Urgency: {urgency_result.urgency_level}")
            print(f"      Score: {urgency_result.urgency_score:.3f}")
            print(f"      Reasoning: {urgency_result.reasoning}")
            
            # Step 6: Save to database
            print(f"  [Step 6/6] Saving to database...")
            async with Session() as session:
                analysis = AmbiguityAnalysis(
                    proposition_id=prop.id,
                    interpretations=format_interpretations_for_storage(interpretations),
                    num_interpretations=len(interpretations),
                    answers=format_answers_for_storage(answers),
                    clusters=format_clusters_for_storage(cluster_result, answer_texts),
                    num_clusters=cluster_result.num_clusters,
                    entropy_score=entropy_result.entropy_score,
                    is_ambiguous=entropy_result.is_ambiguous,
                    threshold_used=entropy_result.threshold_used,
                    model_used=gen_meta['model'],
                    config={
                        'tokens_used': gen_meta['tokens_used'] + ans_meta['total_tokens_used']
                    }
                )
                
                session.add(analysis)
                await session.commit()
                await session.refresh(analysis)
                
                # Save urgency assessment
                urgency_assessment = UrgencyAssessment(
                    proposition_id=prop.id,
                    ambiguity_analysis_id=analysis.id,
                    urgency_level=urgency_result.urgency_level,
                    urgency_score=urgency_result.urgency_score,
                    reasoning=urgency_result.reasoning,
                    time_sensitive=urgency_result.time_sensitive,
                    confidence_factor=urgency_result.confidence_factor,
                    ambiguity_factor=urgency_result.ambiguity_factor,
                    temporal_keywords={'keywords': urgency_result.temporal_keywords},
                    should_clarify_by=urgency_result.should_clarify_by
                )
                
                session.add(urgency_assessment)
                await session.commit()
                
                print(f"    ✓ Saved (Analysis ID: {analysis.id})")
            
            # Store result
            results.append({
                'prop_id': prop.id,
                'confidence': prop.confidence,
                'text_length': len(prop.text),
                'num_interpretations': len(interpretations),
                'num_clusters': cluster_result.num_clusters,
                'entropy': entropy_result.entropy_score,
                'is_ambiguous': entropy_result.is_ambiguous,
                'urgency': urgency_result.urgency_level,
                'urgency_score': urgency_result.urgency_score,
                'tokens_used': gen_meta['tokens_used'] + ans_meta['total_tokens_used'],
                'success': True
            })
            
        except Exception as e:
            print(f"\n    ✗ EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            failures.append({
                'prop_id': prop.id,
                'stage': 'exception',
                'error': str(e)
            })
    
    await engine.dispose()
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Total propositions: {len(propositions)}")
    print(f"Successful: {len(results)}")
    print(f"Failed: {len(failures)}")
    print(f"Success rate: {len(results)/len(propositions)*100:.1f}%")
    
    if results:
        print(f"\n📊 STATISTICS:")
        entropies = [r['entropy'] for r in results]
        print(f"  Entropy range: {min(entropies):.3f} - {max(entropies):.3f} bits")
        print(f"  Average entropy: {np.mean(entropies):.3f} bits")
        
        ambiguous_count = sum(1 for r in results if r['is_ambiguous'])
        print(f"  Ambiguous: {ambiguous_count}/{len(results)} ({ambiguous_count/len(results)*100:.1f}%)")
        
        urgency_dist = {}
        for r in results:
            urgency_dist[r['urgency']] = urgency_dist.get(r['urgency'], 0) + 1
        print(f"  Urgency distribution:")
        for level, count in sorted(urgency_dist.items()):
            print(f"    {level}: {count} ({count/len(results)*100:.1f}%)")
        
        total_tokens = sum(r['tokens_used'] for r in results)
        print(f"  Total tokens used: {total_tokens:,}")
        print(f"  Avg tokens per proposition: {total_tokens/len(results):.0f}")
    
    if failures:
        print(f"\n❌ FAILURES:")
        for f in failures:
            print(f"  Prop {f['prop_id']}: {f['stage']} - {f['error']}")
    
    print(f"\n{'='*80}")
    
    # Save detailed results
    output_file = '/Users/arnavsharma/gum-elicitation/multi_proposition_test_results.json'
    with open(output_file, 'w') as f:
        json.dump({
            'summary': {
                'total': len(propositions),
                'successful': len(results),
                'failed': len(failures),
                'success_rate': len(results)/len(propositions)
            },
            'results': results,
            'failures': failures
        }, f, indent=2)
    
    print(f"Detailed results saved to: {output_file}")
    print(f"{'='*80}")
    
    return len(failures) == 0


async def main():
    """Run test."""
    print("\n🧪 MULTIPLE PROPOSITION TEST\n")
    
    success = await test_multiple_propositions(num_propositions=200)
    
    if success:
        print("\n✅ All propositions processed successfully!")
        return 0
    else:
        print("\n⚠️  Some propositions failed - see details above")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
