#!/usr/bin/env python3
"""
Test 200 propositions with stratified sampling.
Real observations, real API calls, real results - no filtering.
"""

import asyncio
import json
import os
import random
import time
import traceback
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from openai import AsyncOpenAI
from sqlalchemy import select, func

from gum.models import init_db, Proposition
from gum.db_utils import get_related_observations
from gum.clarification import ClarificationDetector
from gum.config import GumConfig


class Batch200Tester:
    """
    Test 200 propositions with stratified sampling.
    No bullshit, all results saved, real observations used.
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = AsyncOpenAI(api_key=api_key)
        self.config = GumConfig()
        
        self.batch_size = 50
        self.total_props = 200
        self.max_cost = 12.0  # Safety limit
        self.seed = 42  # Reproducible
        
        # Create results directory
        self.results_dir = Path("test_results_200_props")
        self.results_dir.mkdir(exist_ok=True)
        
        # Running totals
        self.total_cost = 0.0
        self.total_duration = 0.0
        self.failed_count = 0
        
    async def run(self):
        """Main test execution."""
        print("=" * 80)
        print("200 PROPOSITION TEST - REAL RESULTS ONLY")
        print("=" * 80)
        print(f"Results will be saved to: {self.results_dir}")
        print(f"Max cost limit: ${self.max_cost}")
        print()
        
        # Initialize database
        db_path = Path.home() / ".cache" / "gum" / "gum.db"
        if not db_path.exists():
            print(f"❌ Database not found: {db_path}")
            return
        
        self.engine, self.Session = await init_db(
            db_path=db_path.name,
            db_directory=str(db_path.parent)
        )
        
        print(f"✓ Connected to database: {db_path}\n")
        
        # Sample 200 propositions with stratification
        async with self.Session() as session:
            props = await self._stratified_sample(session, 200)
        
        print(f"\n✓ Selected {len(props)} propositions")
        self._print_sample_stats(props)
        
        # Process in batches
        all_results = []
        
        for batch_num in range(4):  # 4 batches of 50
            batch_props = props[batch_num * 50:(batch_num + 1) * 50]
            
            print(f"\n{'=' * 80}")
            print(f"BATCH {batch_num + 1}/4 ({len(batch_props)} propositions)")
            print(f"{'=' * 80}\n")
            
            batch_results = await self._process_batch(batch_props, batch_num)
            all_results.extend(batch_results)
            
            # Track cost
            batch_cost = sum(r.get('cost_usd', 0) for r in batch_results if 'error' not in r)
            self.total_cost += batch_cost
            
            print(f"\n✓ Batch {batch_num + 1} complete")
            print(f"  - Cost this batch: ${batch_cost:.2f}")
            print(f"  - Total cost so far: ${self.total_cost:.2f}")
            print(f"  - Successful: {sum(1 for r in batch_results if 'error' not in r)}/{len(batch_props)}")
            print(f"  - Failed: {sum(1 for r in batch_results if 'error' in r)}")
            
            # Save checkpoint
            self._save_batch_results(batch_results, batch_num)
            
            # Cost check
            if self.total_cost > self.max_cost:
                print(f"\n⚠️  COST LIMIT EXCEEDED: ${self.total_cost:.2f} > ${self.max_cost}")
                print("Stopping early to avoid excessive costs")
                break
            
            # Rate limiting between batches
            if batch_num < 3:
                print(f"  Sleeping 5s before next batch...")
                await asyncio.sleep(5)
        
        # Compute aggregate statistics
        print(f"\n{'=' * 80}")
        print("COMPUTING AGGREGATE STATISTICS")
        print(f"{'=' * 80}\n")
        
        stats = self._compute_stats(all_results)
        
        # Save all results
        self._save_all_results(all_results, stats)
        
        # Print summary
        self._print_summary(stats)
        
        await self.engine.dispose()
        
        print(f"\n{'=' * 80}")
        print("TEST COMPLETE")
        print(f"{'=' * 80}")
        print(f"Total cost: ${self.total_cost:.2f}")
        print(f"Results saved to: {self.results_dir}")
        print(f"\nKey files:")
        print(f"  - all_results.json         (all 200 proposition analyses)")
        print(f"  - aggregate_stats.json     (summary statistics)")
        print(f"  - flagged_propositions.json (high-scoring props)")
        print(f"  - factor_analysis.json     (per-factor breakdown)")
    
    async def _stratified_sample(self, session, n: int) -> List[Proposition]:
        """
        Sample n propositions with stratification.
        Ensures diversity across confidence levels, lengths, and observation counts.
        """
        random.seed(self.seed)
        
        print("Sampling propositions with stratification...")
        
        # Get all propositions
        result = await session.execute(
            select(Proposition).order_by(Proposition.created_at.desc())
        )
        all_props = result.scalars().all()
        
        print(f"  Total propositions in DB: {len(all_props)}")
        
        # Stratify by confidence
        low_conf = [p for p in all_props if (p.confidence or 5) <= 4]
        med_conf = [p for p in all_props if 5 <= (p.confidence or 5) <= 7]
        high_conf = [p for p in all_props if (p.confidence or 5) >= 8]
        
        print(f"  Low confidence (1-4): {len(low_conf)}")
        print(f"  Med confidence (5-7): {len(med_conf)}")
        print(f"  High confidence (8-10): {len(high_conf)}")
        
        # Sample from each bucket
        n_low = min(50, len(low_conf))
        n_med = min(100, len(med_conf))
        n_high = min(50, len(high_conf))
        
        sampled = (
            random.sample(low_conf, n_low) +
            random.sample(med_conf, n_med) +
            random.sample(high_conf, n_high)
        )
        
        # Shuffle
        random.shuffle(sampled)
        
        return sampled[:n]
    
    def _print_sample_stats(self, props: List[Proposition]):
        """Print statistics about the sampled propositions."""
        
        conf_counts = {
            "low (1-4)": sum(1 for p in props if (p.confidence or 5) <= 4),
            "med (5-7)": sum(1 for p in props if 5 <= (p.confidence or 5) <= 7),
            "high (8-10)": sum(1 for p in props if (p.confidence or 5) >= 8)
        }
        
        length_counts = {
            "short (<100)": sum(1 for p in props if len(p.text) < 100),
            "medium (100-300)": sum(1 for p in props if 100 <= len(p.text) < 300),
            "long (>300)": sum(1 for p in props if len(p.text) >= 300)
        }
        
        print(f"  Confidence distribution:")
        for key, count in conf_counts.items():
            print(f"    - {key}: {count}")
        
        print(f"  Length distribution:")
        for key, count in length_counts.items():
            print(f"    - {key}: {count}")
    
    async def _process_batch(self, batch: List[Proposition], batch_num: int) -> List[Dict]:
        """Process one batch - save EVERY result, no filtering."""
        results = []
        
        for i, prop in enumerate(batch):
            print(f"  [{i+1}/{len(batch)}] Prop #{prop.id}... ", end='', flush=True)
            
            try:
                result = await self._analyze_one(prop)
                results.append(result)
                
                # Show outcome
                if result.get('needs_clarification'):
                    factors = ', '.join(result['triggered_factors'][:2])
                    print(f"🚨 FLAGGED (score={result['clarification_score']:.2f}, {factors})")
                else:
                    print(f"✓ OK (score={result['clarification_score']:.2f})")
                
            except Exception as e:
                error_msg = str(e)[:80]
                print(f"❌ ERROR: {error_msg}")
                results.append({
                    "prop_id": prop.id,
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })
                self.failed_count += 1
            
            # Rate limiting
            await asyncio.sleep(0.5)
        
        return results
    
    async def _analyze_one(self, prop: Proposition) -> Dict[str, Any]:
        """Analyze one proposition with REAL observations - capture EVERYTHING."""
        start_time = time.time()
        
        async with self.Session() as session:
            # Load ACTUAL observations from database
            observations = await get_related_observations(session, prop.id, limit=20)
            
            # Run the detector (which uses the observations in the prompt)
            detector = ClarificationDetector(self.client, self.config)
            analysis = await detector.analyze(prop, session)
            
            duration = time.time() - start_time
            self.total_duration += duration
            
            # Estimate cost (will be more accurate from API response if we capture it)
            # Rough estimate: ~3000 tokens prompt + ~1000 completion = 4000 total
            estimated_tokens = 4000
            cost = estimated_tokens * 0.00001  # GPT-4-turbo pricing
            
            # Build complete result
            return {
                "prop_id": prop.id,
                "prop_text": prop.text,
                "prop_text_preview": prop.text[:100] + "..." if len(prop.text) > 100 else prop.text,
                "prop_confidence": prop.confidence,
                "prop_length": len(prop.text),
                "prop_reasoning": prop.reasoning[:100] + "..." if prop.reasoning and len(prop.reasoning) > 100 else prop.reasoning,
                
                # Observations
                "observation_count": len(observations),
                "observation_previews": [obs.content[:100] for obs in observations[:3]],
                
                # Analysis results
                "clarification_score": analysis.clarification_score,
                "needs_clarification": analysis.needs_clarification,
                "triggered_factors": analysis.triggered_factors.get("factors", []),
                "factor_scores": {
                    "identity_mismatch": analysis.factor_1_identity,
                    "surveillance": analysis.factor_2_surveillance,
                    "inferred_intent": analysis.factor_3_intent,
                    "face_threat": analysis.factor_4_face_threat,
                    "over_positive": analysis.factor_5_over_positive,
                    "opacity": analysis.factor_6_opacity,
                    "generalization": analysis.factor_7_generalization,
                    "privacy": analysis.factor_8_privacy,
                    "actor_observer": analysis.factor_9_actor_observer,
                    "reputation_risk": analysis.factor_10_reputation,
                    "ambiguity": analysis.factor_11_ambiguity,
                    "tone_imbalance": analysis.factor_12_tone,
                },
                
                # Validation
                "validation_passed": analysis.validation_passed,
                "reasoning_log": analysis.reasoning_log,
                
                # Performance
                "duration_seconds": duration,
                "estimated_tokens": estimated_tokens,
                "cost_usd": cost,
                
                # Metadata
                "model_used": analysis.model_used,
                "timestamp": datetime.now().isoformat(),
                
                # Raw LLM output (for auditing)
                "llm_raw_output": analysis.llm_raw_output
            }
    
    def _save_batch_results(self, results: List[Dict], batch_num: int):
        """Save batch results as checkpoint."""
        filename = self.results_dir / f"batch_{batch_num}_results.json"
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"  Saved checkpoint: {filename}")
    
    def _compute_stats(self, results: List[Dict]) -> Dict[str, Any]:
        """Compute aggregate statistics from all results."""
        
        # Filter out errors
        successful = [r for r in results if 'error' not in r]
        failed = [r for r in results if 'error' in r]
        
        if not successful:
            return {"error": "No successful analyses"}
        
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
        flagged = [r for r in successful if r['needs_clarification']]
        
        # Factor trigger counts
        factor_counts = {}
        for r in successful:
            for factor in r['triggered_factors']:
                factor_counts[factor] = factor_counts.get(factor, 0) + 1
        
        # Average factor scores
        factor_score_sums = {}
        for r in successful:
            for factor_name, score in r['factor_scores'].items():
                factor_score_sums[factor_name] = factor_score_sums.get(factor_name, 0) + score
        
        factor_score_avgs = {
            name: total / len(successful)
            for name, total in factor_score_sums.items()
        }
        
        # Validation stats
        validation_pass_count = sum(1 for r in successful if r.get('validation_passed'))
        
        # Cost stats
        total_cost = sum(r.get('cost_usd', 0) for r in successful)
        avg_cost = total_cost / len(successful) if successful else 0
        
        # Confidence vs score correlation
        conf_score_pairs = [
            (r['prop_confidence'] or 5, r['clarification_score'])
            for r in successful if r['prop_confidence'] is not None
        ]
        
        return {
            "test_metadata": {
                "total_tested": len(results),
                "successful": len(successful),
                "failed": len(failed),
                "seed": self.seed,
                "timestamp": datetime.now().isoformat()
            },
            "cost": {
                "total_usd": total_cost,
                "avg_per_prop": avg_cost,
                "estimated_total_tokens": sum(r.get('estimated_tokens', 0) for r in successful)
            },
            "performance": {
                "total_duration_seconds": self.total_duration,
                "avg_duration_per_prop": self.total_duration / len(successful) if successful else 0
            },
            "score_distribution": score_buckets,
            "flagging": {
                "flagged_count": len(flagged),
                "flagged_rate": len(flagged) / len(successful) if successful else 0,
                "avg_flagged_score": sum(r['clarification_score'] for r in flagged) / len(flagged) if flagged else 0
            },
            "factor_trigger_counts": dict(sorted(factor_counts.items(), key=lambda x: x[1], reverse=True)),
            "factor_avg_scores": dict(sorted(factor_score_avgs.items(), key=lambda x: x[1], reverse=True)),
            "validation": {
                "pass_count": validation_pass_count,
                "pass_rate": validation_pass_count / len(successful) if successful else 0
            },
            "top_flagged_props": [
                {
                    "prop_id": r['prop_id'],
                    "score": r['clarification_score'],
                    "factors": r['triggered_factors'],
                    "text_preview": r['prop_text_preview']
                }
                for r in sorted(successful, key=lambda x: x['clarification_score'], reverse=True)[:10]
            ]
        }
    
    def _save_all_results(self, results: List[Dict], stats: Dict):
        """Save all results and statistics."""
        
        # All results
        with open(self.results_dir / "all_results.json", 'w') as f:
            json.dump(results, f, indent=2)
        
        # Aggregate stats
        with open(self.results_dir / "aggregate_stats.json", 'w') as f:
            json.dump(stats, f, indent=2)
        
        # Flagged propositions only
        flagged = [r for r in results if r.get('needs_clarification') and 'error' not in r]
        with open(self.results_dir / "flagged_propositions.json", 'w') as f:
            json.dump(flagged, f, indent=2)
        
        # Factor analysis
        factor_analysis = {
            "trigger_counts": stats.get('factor_trigger_counts', {}),
            "avg_scores": stats.get('factor_avg_scores', {})
        }
        with open(self.results_dir / "factor_analysis.json", 'w') as f:
            json.dump(factor_analysis, f, indent=2)
        
        print(f"\n✓ Saved all results to {self.results_dir}")
    
    def _print_summary(self, stats: Dict):
        """Print summary statistics."""
        print("\n📊 SUMMARY STATISTICS")
        print("=" * 80)
        
        print(f"\n✓ Tested: {stats['test_metadata']['successful']}/{stats['test_metadata']['total_tested']} successful")
        print(f"✓ Total cost: ${stats['cost']['total_usd']:.2f}")
        print(f"✓ Avg cost per prop: ${stats['cost']['avg_per_prop']:.4f}")
        
        print(f"\n📈 Score Distribution:")
        for bucket, count in stats['score_distribution'].items():
            pct = count / stats['test_metadata']['successful'] * 100
            print(f"  {bucket}: {count:3d} ({pct:5.1f}%)")
        
        print(f"\n🚨 Flagging:")
        print(f"  Flagged: {stats['flagging']['flagged_count']} ({stats['flagging']['flagged_rate']*100:.1f}%)")
        print(f"  Avg flagged score: {stats['flagging']['avg_flagged_score']:.2f}")
        
        print(f"\n🔍 Top Triggered Factors:")
        for factor, count in list(stats['factor_trigger_counts'].items())[:5]:
            print(f"  {factor}: {count}")
        
        print(f"\n✅ Validation:")
        print(f"  Pass rate: {stats['validation']['pass_rate']*100:.1f}%")


async def main():
    """Main entry point."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    tester = Batch200Tester(api_key)
    await tester.run()


if __name__ == "__main__":
    asyncio.run(main())

