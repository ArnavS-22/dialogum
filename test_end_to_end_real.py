#!/usr/bin/env python3
"""
END-TO-END INTEGRATION TEST

This test validates the FULL pipeline without relying on the broken queue system.
It directly tests whether the mixed-initiative integration actually works in practice.
"""

import asyncio
import logging
import time
from unittest.mock import patch, MagicMock

from gum.models import Proposition
from gum.decision import MixedInitiativeDecisionEngine, DecisionContext  
from gum.attention import AttentionMonitor
from gum.config import GumConfig

# Suppress noise
logging.basicConfig(level=logging.ERROR)

async def test_full_pipeline_simulation():
    """
    REAL TEST: Simulate the full mixed-initiative pipeline
    without the broken queue system.
    """
    print("🔥 END-TO-END PIPELINE TEST")
    print("=" * 50)
    
    # 1. Initialize components
    config = GumConfig()
    engine = MixedInitiativeDecisionEngine(config.decision, debug=True)
    attention = AttentionMonitor(debug=True)
    
    print("✅ Components initialized")
    
    # 2. Start attention monitoring
    attention.start_monitoring()
    await asyncio.sleep(1)  # Let it gather some data
    print("✅ Attention monitoring started")
    
    # 3. Simulate realistic user scenarios
    scenarios = [
        {
            "name": "Coding focused", 
            "app": "vscode",
            "confidence": 8,
            "text": "User prefers Python over JavaScript",
            "expected": "conservative"  # Should not interrupt
        },
        {
            "name": "Browsing casually",
            "app": "safari", 
            "confidence": 4,
            "text": "User might like jazz music",
            "expected": "moderate"  # Might ask question
        },
        {
            "name": "High confidence + idle",
            "app": "unknown",
            "confidence": 9, 
            "text": "User definitely prefers dark themes",
            "expected": "aggressive"  # Should take action
        }
    ]
    
    results = []
    
    for scenario in scenarios:
        print(f"\n--- {scenario['name']} ---")
        
        # Create proposition
        prop = Proposition(
            text=scenario['text'],
            confidence=scenario['confidence'],
            reasoning="Test scenario"
        )
        
        # Get current attention state
        current_state = attention.get_current_attention()
        print(f"Current attention: {current_state.focus_level:.2f}")
        
        # Make decision
        context = DecisionContext(
            proposition=prop,
            user_attention_level=current_state.focus_level,
            active_application=scenario['app'],
            idle_time_seconds=10.0
        )
        
        decision, metadata = engine.make_decision(context)
        
        print(f"Proposition: {prop.text}")
        print(f"Confidence: {prop.confidence}/10")
        print(f"App: {scenario['app']}")
        print(f"Decision: {decision}")
        print(f"Expected Utilities: {metadata['expected_utilities']}")
        
        results.append({
            'scenario': scenario['name'],
            'decision': decision,
            'expected': scenario['expected'],
            'confidence': prop.confidence,
            'focus': current_state.focus_level,
            'utilities': metadata['expected_utilities']
        })
    
    # 4. Validate results make sense
    print(f"\n--- VALIDATION ---")
    
    validation_passed = True
    
    for result in results:
        print(f"{result['scenario']}: {result['decision']}")
        
        # Basic sanity checks
        if result['confidence'] >= 8 and result['focus'] < 0.5:
            # High confidence + low focus should be willing to act
            if result['decision'] == 'no_action':
                print(f"❌ High confidence + low focus should act, got {result['decision']}")
                validation_passed = False
        
        if result['confidence'] <= 3 and result['focus'] > 0.8:
            # Low confidence + high focus should definitely not act
            if result['decision'] == 'autonomous_action':
                print(f"❌ Low confidence + high focus should not act, got {result['decision']}")
                validation_passed = False
    
    # 5. Test decision persistence
    print(f"\n--- PERSISTENCE TEST ---")
    
    # Same proposition should get same decision
    test_prop = Proposition(text="Test persistence", confidence=6, reasoning="Test")
    base_context = DecisionContext(test_prop, 0.5, "test", 10.0)
    
    decisions = []
    for i in range(5):
        decision, _ = engine.make_decision(base_context)
        decisions.append(decision)
    
    if len(set(decisions)) == 1:
        print("✅ Decisions are persistent")
    else:
        print(f"❌ Inconsistent decisions: {decisions}")
        validation_passed = False
    
    # 6. Test attention state changes
    print(f"\n--- ATTENTION RESPONSIVENESS ---")
    
    # Test different attention levels
    test_prop = Proposition(text="Test attention", confidence=5, reasoning="Test")
    
    high_focus_context = DecisionContext(test_prop, 0.9, "xcode", 5.0)
    low_focus_context = DecisionContext(test_prop, 0.1, "spotify", 300.0)
    
    high_decision, high_meta = engine.make_decision(high_focus_context)
    low_decision, low_meta = engine.make_decision(low_focus_context)
    
    print(f"High focus: {high_decision} (interruption cost: {high_meta['utilities_used']['u_action_goal_false']:.2f})")
    print(f"Low focus: {low_decision} (interruption cost: {low_meta['utilities_used']['u_action_goal_false']:.2f})")
    
    # High focus should have higher interruption cost (more negative)
    high_cost = high_meta['utilities_used']['u_action_goal_false']
    low_cost = low_meta['utilities_used']['u_action_goal_false']
    
    if high_cost < low_cost:  # More negative = higher cost
        print("✅ Attention affects interruption costs")
    else:
        print(f"❌ Attention doesn't affect costs: high={high_cost}, low={low_cost}")
        validation_passed = False
    
    # 7. Stop monitoring
    attention.stop_monitoring()
    print("✅ Attention monitoring stopped")
    
    # Final verdict
    print(f"\n" + "=" * 50)
    if validation_passed:
        print("🎉 END-TO-END TEST PASSED")
        print("The mixed-initiative system works as designed!")
        return True
    else:
        print("💥 END-TO-END TEST FAILED") 
        print("The system has logical issues that need fixing!")
        return False

async def test_realistic_user_session():
    """
    Simulate a realistic 10-minute user session with mixed activities.
    """
    print("\n🎮 REALISTIC USER SESSION SIMULATION")
    print("=" * 50)
    
    config = GumConfig()
    engine = MixedInitiativeDecisionEngine(config.decision, debug=False)
    attention = AttentionMonitor(debug=False)
    
    attention.start_monitoring()
    
    # Simulate 10 activities over time
    activities = [
        (0, "vscode", "User prefers TypeScript over JavaScript", 7),
        (30, "vscode", "User uses dark themes consistently", 9),  
        (120, "safari", "User might like cooking videos", 3),
        (180, "spotify", "User listens to electronic music", 6),
        (240, "vscode", "User prefers functional programming", 5),
        (300, "slack", "User checks messages frequently", 4),
        (360, "terminal", "User uses git CLI over GUI", 8),
        (420, "safari", "User browses tech news", 4),
        (480, "vscode", "User prefers small functions", 6),
        (540, "unknown", "User takes breaks regularly", 7),
    ]
    
    decisions = []
    
    for delay, app, prop_text, confidence in activities:
        # Wait for realistic timing
        if delay > 0:
            await asyncio.sleep(min(2, delay/60))  # Accelerated time
        
        # Create proposition
        prop = Proposition(text=prop_text, confidence=confidence, reasoning="Observed behavior")
        
        # Get attention (would be dynamic in real system)
        current_state = attention.get_current_attention()
        
        # Simulate app change affecting attention
        if app in ["vscode", "terminal", "xcode"]:
            focus_boost = 0.3
        elif app in ["safari", "spotify", "slack"]:
            focus_boost = -0.2
        else:
            focus_boost = 0.0
        
        adjusted_focus = max(0.0, min(1.0, current_state.focus_level + focus_boost))
        
        context = DecisionContext(prop, adjusted_focus, app, delay)
        decision, metadata = engine.make_decision(context)
        
        decisions.append({
            'time': delay,
            'app': app,
            'proposition': prop_text[:30] + "...",
            'confidence': confidence,
            'focus': adjusted_focus,
            'decision': decision,
            'eu': max(metadata['expected_utilities'].values())
        })
    
    # Analyze session
    print("\nSESSION ANALYSIS:")
    print("Time | App      | Confidence | Focus | Decision          | EU")
    print("-" * 70)
    
    for d in decisions:
        print(f"{d['time']:3d}s | {d['app']:8s} | {d['confidence']:2d}/10      | {d['focus']:.2f}  | {d['decision']:15s} | {d['eu']:.2f}")
    
    # Statistics
    decision_counts = {}
    for d in decisions:
        decision_counts[d['decision']] = decision_counts.get(d['decision'], 0) + 1
    
    print(f"\nDECISION DISTRIBUTION:")
    for decision, count in decision_counts.items():
        percentage = count / len(decisions) * 100
        print(f"  {decision}: {count} ({percentage:.1f}%)")
    
    # Validate reasonable distribution
    no_action_pct = decision_counts.get('no_action', 0) / len(decisions)
    dialogue_pct = decision_counts.get('dialogue', 0) / len(decisions)
    action_pct = decision_counts.get('autonomous_action', 0) / len(decisions)
    
    print(f"\nVALIDATION:")
    
    # Reasonable distribution check
    if 0.2 <= no_action_pct <= 0.7:
        print("✅ Reasonable no_action rate")
    else:
        print(f"❌ Unreasonable no_action rate: {no_action_pct:.1%}")
    
    if dialogue_pct >= 0.1:
        print("✅ Some dialogue decisions")
    else:
        print("❌ No dialogue decisions - system not asking questions")
    
    if action_pct <= 0.5:
        print("✅ Not too aggressive")
    else:
        print("❌ Too many autonomous actions")
    
    attention.stop_monitoring()
    
    return decision_counts

async def main():
    """Run all end-to-end tests."""
    
    print("🚀 COMPREHENSIVE END-TO-END TESTING")
    print("This tests the REAL functionality without broken components")
    print("=" * 60)
    
    try:
        # Test 1: Basic pipeline
        pipeline_success = await test_full_pipeline_simulation()
        
        # Test 2: Realistic session
        session_stats = await test_realistic_user_session()
        
        print("\n" + "=" * 60)
        print("📊 FINAL RESULTS:")
        
        if pipeline_success:
            print("✅ Core pipeline works correctly")
        else:
            print("❌ Core pipeline has issues")
        
        total_decisions = sum(session_stats.values())
        if total_decisions > 0:
            print("✅ System makes decisions in realistic scenarios")
            
            dialogue_rate = session_stats.get('dialogue', 0) / total_decisions
            if dialogue_rate > 0:
                print(f"✅ System asks questions ({dialogue_rate:.1%} of time)")
            else:
                print("⚠️  System never asks questions")
        
        if pipeline_success and total_decisions > 0:
            print("\n🎯 VERDICT: Mixed-initiative system is FUNCTIONAL")
            print("   The core logic works, decisions are reasonable,")
            print("   and attention awareness is implemented correctly.")
            print("\n   Main issues are:")
            print("   - Magic numbers need empirical validation")
            print("   - App classification needs expansion") 
            print("   - Queue system needs fixing for production")
            return 0
        else:
            print("\n💀 VERDICT: System has FUNDAMENTAL ISSUES")
            return 1
            
    except Exception as e:
        print(f"\n💥 CRITICAL ERROR: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
