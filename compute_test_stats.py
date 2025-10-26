#!/usr/bin/env python3
"""
Compute statistics from the 150 proposition test results.
Reads from saved batch files since the test crashed before computing stats.
"""

import json
from pathlib import Path
from collections import Counter

results_dir = Path("test_results_200_props")

# Load all batch results
all_results = []
for i in range(4):
    batch_file = results_dir / f"batch_{i}_results.json"
    if batch_file.exists():
        with open(batch_file) as f:
            batch_data = json.load(f)
            all_results.extend(batch_data)
            print(f"Loaded {len(batch_data)} results from batch {i}")

print(f"\nTotal results loaded: {len(all_results)}")

# Filter out errors
successful = [r for r in all_results if 'error' not in r and r.get('clarification_score') is not None]
failed = [r for r in all_results if 'error' in r or r.get('clarification_score') is None]

print(f"Successful: {len(successful)}")
print(f"Failed: {len(failed)}")

if not successful:
    print("\n❌ No successful analyses to compute stats from")
    exit(1)

# Score distribution
scores = [r['clarification_score'] for r in successful]
score_buckets = {
    "0.0-0.2": sum(1 for s in scores if s < 0.2),
    "0.2-0.4": sum(1 for s in scores if 0.2 <= s < 0.4),
    "0.4-0.6": sum(1 for s in scores if 0.4 <= s < 0.6),
    "0.6-0.8": sum(1 for s in scores if 0.6 <= s < 0.8),
    "0.8-1.0": sum(1 for s in scores if s >= 0.8)
}

# Flagged count
flagged = [r for r in successful if r.get('needs_clarification')]

# Factor trigger counts
factor_counts = Counter()
for r in successful:
    for factor in r.get('triggered_factors', []):
        factor_counts[factor] += 1

# Average factor scores (handling None values)
factor_score_sums = {}
factor_score_counts = {}
for r in successful:
    for factor_name, score in r.get('factor_scores', {}).items():
        if score is not None:
            factor_score_sums[factor_name] = factor_score_sums.get(factor_name, 0) + score
            factor_score_counts[factor_name] = factor_score_counts.get(factor_name, 0) + 1

factor_score_avgs = {
    name: factor_score_sums[name] / factor_score_counts[name]
    for name in factor_score_sums.keys()
}

# Cost stats
total_cost = sum(r.get('cost_usd', 0) for r in successful)
avg_cost = total_cost / len(successful)

# Validation stats
validation_pass_count = sum(1 for r in successful if r.get('validation_passed'))

# Compile stats
stats = {
    "test_metadata": {
        "total_tested": len(all_results),
        "successful": len(successful),
        "failed": len(failed),
    },
    "cost": {
        "total_usd": round(total_cost, 2),
        "avg_per_prop": round(avg_cost, 4),
    },
    "score_distribution": score_buckets,
    "flagging": {
        "flagged_count": len(flagged),
        "flagged_rate": round(len(flagged) / len(successful), 3),
        "avg_flagged_score": round(sum(r['clarification_score'] for r in flagged) / len(flagged), 2) if flagged else 0
    },
    "factor_trigger_counts": dict(factor_counts.most_common()),
    "factor_avg_scores": {k: round(v, 3) for k, v in sorted(factor_score_avgs.items(), key=lambda x: x[1], reverse=True)},
    "validation": {
        "pass_count": validation_pass_count,
        "pass_rate": round(validation_pass_count / len(successful), 3)
    },
    "top_flagged_props": [
        {
            "prop_id": r['prop_id'],
            "score": r['clarification_score'],
            "factors": r.get('triggered_factors', []),
            "text_preview": r.get('prop_text_preview', '')
        }
        for r in sorted(successful, key=lambda x: x.get('clarification_score', 0), reverse=True)[:10]
    ]
}

# Save stats
with open(results_dir / "aggregate_stats.json", 'w') as f:
    json.dump(stats, f, indent=2)

# Save flagged only
with open(results_dir / "flagged_propositions.json", 'w') as f:
    json.dump(flagged, f, indent=2)

# Print summary
print("\n" + "="*80)
print("SUMMARY STATISTICS")
print("="*80)

print(f"\n✓ Tested: {stats['test_metadata']['successful']}/{stats['test_metadata']['total_tested']} successful")
print(f"✓ Total cost: ${stats['cost']['total_usd']}")
print(f"✓ Avg cost per prop: ${stats['cost']['avg_per_prop']}")

print(f"\n📈 Score Distribution:")
for bucket, count in stats['score_distribution'].items():
    pct = count / stats['test_metadata']['successful'] * 100
    bar = "█" * (count // 2)
    print(f"  {bucket}: {count:3d} ({pct:5.1f}%) {bar}")

print(f"\n🚨 Flagging:")
print(f"  Flagged: {stats['flagging']['flagged_count']} ({stats['flagging']['flagged_rate']*100:.1f}%)")
print(f"  Avg flagged score: {stats['flagging']['avg_flagged_score']}")

print(f"\n🔍 Top 10 Triggered Factors:")
for factor, count in list(stats['factor_trigger_counts'].items())[:10]:
    pct = count / stats['test_metadata']['successful'] * 100
    print(f"  {factor:25s}: {count:3d} ({pct:5.1f}%)")

print(f"\n📊 Factor Average Scores (Top 5):")
for factor, avg_score in list(stats['factor_avg_scores'].items())[:5]:
    print(f"  {factor:25s}: {avg_score:.3f}")

print(f"\n✅ Validation:")
print(f"  Pass rate: {stats['validation']['pass_rate']*100:.1f}%")

print(f"\n🎯 Top 10 Flagged Propositions:")
for i, prop in enumerate(stats['top_flagged_props'], 1):
    factors_str = ', '.join(prop['factors'][:3])
    print(f"  {i:2d}. Prop #{prop['prop_id']}: {prop['score']:.2f} - {factors_str}")
    print(f"      \"{prop['text_preview'][:70]}...\"")

print(f"\n✅ Results saved to {results_dir}/")
print(f"   - aggregate_stats.json")
print(f"   - flagged_propositions.json")

