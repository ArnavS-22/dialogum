#!/usr/bin/env python3
"""
Validate our ambiguity detection pipeline against the AmbiEnt dataset.
This will tell us if our entropy-based approach correlates with expert annotations.
"""
import json
import asyncio
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from gum.models import init_db
from gum.ambiguity.interpretation_generator import InterpretationGenerator
from gum.ambiguity.answer_collector import AnswerCollector, get_answer_texts
from gum.ambiguity.clustering import SemanticClusterer
from gum.ambiguity.entropy_calculator import EntropyCalculator
from gum.ambiguity.urgency_detector import UrgencyDetector

async def test_on_ambient_dataset(max_examples=50):
    """
    Run our pipeline on AmbiEnt examples and compare against expert labels.
    """
    print("=" * 80)
    print("VALIDATING AGAINST AMBIENT DATASET")
    print("=" * 80)
    print()
    
    # Load AmbiEnt dev set
    ambient_path = Path("reference_implementations/ambient/AmbiEnt/dev.jsonl")
    with open(ambient_path) as f:
        ambient_examples = [json.loads(line) for line in f]
    
    print(f"Loaded {len(ambient_examples)} AmbiEnt examples")
    
    # Take subset for testing
    test_examples = ambient_examples[:max_examples]
    print(f"Testing on {len(test_examples)} examples")
    print()
    
    # Initialize modules
    print("Initializing pipeline modules...")
    generator = InterpretationGenerator()
    collector = AnswerCollector()
    clusterer = SemanticClusterer()
    entropy_calc = EntropyCalculator()
    urgency_detector = UrgencyDetector()
    print("✓ All modules ready")
    print()
    
    results = []
    failures = []
    
    for i, example in enumerate(test_examples, 1):
        print(f"\n{'='*60}")
        print(f"EXAMPLE {i}/{len(test_examples)} - ID: {example['id']}")
        print(f"{'='*60}")
        
        # Test both premise and hypothesis
        for text_type in ['premise', 'hypothesis']:
            text = example[text_type]
            expert_ambiguous = example.get(f'{text_type}_ambiguous', False)
            
            print(f"\n{text_type.upper()}: {text}")
            print(f"Expert label: {'AMBIGUOUS' if expert_ambiguous else 'CLEAR'}")
            
            try:
                # Run our pipeline
                print("  Running pipeline...")
                
                # Step 1: Generate interpretations
                interpretations, gen_meta = await generator.generate_async(
                    proposition_text=text,
                    reasoning="",
                    confidence=8  # Default confidence
                )
                
                if not gen_meta['success'] or len(interpretations) == 0:
                    print(f"    ✗ Failed to generate interpretations")
                    failures.append({
                        'id': example['id'],
                        'text_type': text_type,
                        'stage': 'interpretation',
                        'error': 'No interpretations generated'
                    })
                    continue
                
                print(f"    ✓ Generated {len(interpretations)} interpretations")
                
                # Step 2: Collect answers
                answers, ans_meta = await collector.collect_answers_async(
                    interpretations=interpretations,
                    proposition_text=text,
                    reasoning="",
                    num_answers_per_interpretation=5
                )
                
                if not ans_meta['success'] or ans_meta['successful_answers'] == 0:
                    print(f"    ✗ Failed to collect answers")
                    failures.append({
                        'id': example['id'],
                        'text_type': text_type,
                        'stage': 'answers',
                        'error': 'No successful answers'
                    })
                    continue
                
                print(f"    ✓ Collected {ans_meta['successful_answers']} answers")
                
                # Step 3: Cluster
                answer_texts = get_answer_texts(answers)
                if len(answer_texts) < 2:
                    print(f"    ✗ Not enough answers for clustering: {len(answer_texts)}")
                    failures.append({
                        'id': example['id'],
                        'text_type': text_type,
                        'stage': 'clustering',
                        'error': f'Only {len(answer_texts)} valid answers'
                    })
                    continue
                
                cluster_result = clusterer.cluster(answer_texts)
                print(f"    ✓ Found {cluster_result.num_clusters} clusters")
                
                # Step 4: Calculate entropy
                entropy_result = entropy_calc.calculate(cluster_result)
                print(f"    ✓ Entropy: {entropy_result.entropy_score:.3f} bits")
                print(f"    ✓ Our prediction: {'AMBIGUOUS' if entropy_result.is_ambiguous else 'CLEAR'}")
                
                # Step 5: Compare with expert label
                our_prediction = entropy_result.is_ambiguous
                correct = our_prediction == expert_ambiguous
                
                print(f"    {'✓' if correct else '✗'} {'CORRECT' if correct else 'INCORRECT'}")
                
                # Store result
                results.append({
                    'id': example['id'],
                    'text_type': text_type,
                    'text': text,
                    'expert_ambiguous': expert_ambiguous,
                    'our_ambiguous': our_prediction,
                    'entropy_score': entropy_result.entropy_score,
                    'threshold': entropy_result.threshold_used,
                    'num_interpretations': len(interpretations),
                    'num_clusters': cluster_result.num_clusters,
                    'correct': correct
                })
                
            except Exception as e:
                print(f"    ✗ EXCEPTION: {e}")
                failures.append({
                    'id': example['id'],
                    'text_type': text_type,
                    'stage': 'exception',
                    'error': str(e)
                })
    
    # Calculate metrics
    print(f"\n{'='*80}")
    print("VALIDATION RESULTS")
    print(f"{'='*80}")
    
    if not results:
        print("❌ No successful results to analyze!")
        return
    
    # Extract predictions and ground truth
    y_true = [r['expert_ambiguous'] for r in results]
    y_pred = [r['our_ambiguous'] for r in results]
    entropy_scores = [r['entropy_score'] for r in results]
    
    # Basic accuracy
    correct_count = sum(1 for r in results if r['correct'])
    accuracy = correct_count / len(results)
    
    print(f"Total examples processed: {len(results)}")
    print(f"Accuracy: {accuracy:.3f} ({correct_count}/{len(results)})")
    print()
    
    # Manual confusion matrix calculation
    tp = sum(1 for i in range(len(y_true)) if y_true[i] and y_pred[i])
    fp = sum(1 for i in range(len(y_true)) if not y_true[i] and y_pred[i])
    fn = sum(1 for i in range(len(y_true)) if y_true[i] and not y_pred[i])
    tn = sum(1 for i in range(len(y_true)) if not y_true[i] and not y_pred[i])
    
    # Calculate metrics
    if tp + fp > 0:
        precision = tp / (tp + fp)
    else:
        precision = 0.0
        
    if tp + fn > 0:
        recall = tp / (tp + fn)
    else:
        recall = 0.0
        
    if precision + recall > 0:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = 0.0
    
    print(f"Precision: {precision:.3f}")
    print(f"Recall:    {recall:.3f}")
    print(f"F1 Score:  {f1:.3f}")
    print()
    
    print("Confusion Matrix:")
    print(f"  True Negatives (Clear→Clear):   {tn}")
    print(f"  False Positives (Clear→Ambig):  {fp}")
    print(f"  False Negatives (Ambig→Clear):  {fn}")
    print(f"  True Positives (Ambig→Ambig):   {tp}")
    print()
        
    # Distribution analysis
    expert_ambig_count = sum(y_true)
    our_ambig_count = sum(y_pred)
    
    print("Label Distribution:")
    print(f"  Expert labeled ambiguous: {expert_ambig_count}/{len(results)} ({expert_ambig_count/len(results)*100:.1f}%)")
    print(f"  Our system labeled ambiguous: {our_ambig_count}/{len(results)} ({our_ambig_count/len(results)*100:.1f}%)")
    print()
    
    # Entropy analysis
    ambig_entropies = [r['entropy_score'] for r in results if r['expert_ambiguous']]
    clear_entropies = [r['entropy_score'] for r in results if not r['expert_ambiguous']]
    
    if ambig_entropies and clear_entropies:
        print("Entropy Analysis:")
        print(f"  Ambiguous examples - Mean entropy: {np.mean(ambig_entropies):.3f} ± {np.std(ambig_entropies):.3f}")
        print(f"  Clear examples - Mean entropy: {np.mean(clear_entropies):.3f} ± {np.std(clear_entropies):.3f}")
        print()
        
        # Find optimal threshold
        thresholds = [i/10.0 for i in range(1, 31)]  # 0.1 to 3.0 in steps of 0.1
        best_f1 = 0
        best_threshold = 0.8
        
        for threshold in thresholds:
            pred_at_threshold = [entropy >= threshold for entropy in entropy_scores]
            if len(set(pred_at_threshold)) > 1:
                # Calculate F1 manually
                tp_t = sum(1 for i in range(len(y_true)) if y_true[i] and pred_at_threshold[i])
                fp_t = sum(1 for i in range(len(y_true)) if not y_true[i] and pred_at_threshold[i])
                fn_t = sum(1 for i in range(len(y_true)) if y_true[i] and not pred_at_threshold[i])
                
                if tp_t + fp_t > 0 and tp_t + fn_t > 0:
                    prec_t = tp_t / (tp_t + fp_t)
                    rec_t = tp_t / (tp_t + fn_t)
                    if prec_t + rec_t > 0:
                        f1_t = 2 * prec_t * rec_t / (prec_t + rec_t)
                        if f1_t > best_f1:
                            best_f1 = f1_t
                            best_threshold = threshold
        
        print(f"Optimal threshold: {best_threshold:.3f} (F1: {best_f1:.3f})")
        print(f"Current threshold: {results[0]['threshold']:.3f}")
        print()
    
    if failures:
        print(f"❌ FAILURES ({len(failures)}):")
        for f in failures:
            print(f"  {f['id']} ({f['text_type']}): {f['stage']} - {f['error']}")
        print()
    
    # Save detailed results
    output_file = 'ambient_validation_results.json'
    with open(output_file, 'w') as f:
        json.dump({
            'summary': {
                'total_processed': len(results),
                'accuracy': accuracy,
                'expert_ambiguous_rate': expert_ambig_count / len(results) if results else 0,
                'our_ambiguous_rate': our_ambig_count / len(results) if results else 0,
                'precision': precision if 'precision' in locals() else None,
                'recall': recall if 'recall' in locals() else None,
                'f1': f1 if 'f1' in locals() else None,
                'optimal_threshold': best_threshold if 'best_threshold' in locals() else None,
                'current_threshold': results[0]['threshold'] if results else None
            },
            'results': results,
            'failures': failures
        }, f, indent=2)
    
    print(f"Detailed results saved to: {output_file}")
    print("=" * 80)

async def main():
    print("\n🔬 AMBIENT DATASET VALIDATION\n")
    await test_on_ambient_dataset(max_examples=30)  # Start with 30 examples

if __name__ == "__main__":
    asyncio.run(main())