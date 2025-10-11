#!/usr/bin/env python3
"""
REAL FUNCTIONALITY TEST for Mixed-Initiative Decision Engine

This test exposes whether the system actually works in practice
by simulating realistic user scenarios and validating decisions.

Unlike the bullshit "production tests", this actually tests:
1. Real decision quality under realistic scenarios  
2. Consistency of decisions across similar contexts
3. Attention calculation accuracy
4. Performance under load
5. Integration with actual GUM pipeline
"""

import asyncio
import logging
import time
import statistics
from typing import List, Dict, Tuple
from dataclasses import dataclass

# Mixed-initiative engine removed; skip tests using it
import pytest
pytest.skip("Mixed-initiative engine removed", allow_module_level=True)
from gum.models import Proposition
from gum.config import GumConfig

# Configure logging
logging.basicConfig(level=logging.WARNING)

@dataclass
class TestScenario:
    name: str
    proposition_text: str
    confidence: int
    attention_level: float
    active_app: str
    expected_decision_type: str  # "conservative", "moderate", "aggressive"
    context: str

class RealFunctionalityTester:
    """Tests that expose real functionality issues."""
    
    def __init__(self):
        self.engine = MixedInitiativeDecisionEngine(debug=False)
        self.attention_monitor = AttentionMonitor(debug=False)
        self.results = []
    
    def test_decision_consistency(self) -> bool:
        """
        TEST 1: Decision Consistency
        Do identical scenarios produce identical decisions?
        """
        print("🧪 TEST 1: Decision Consistency")
        
        # Create identical scenarios
        base_prop = Proposition(
            text="User prefers dark mode themes",
            confidence=7,
            reasoning="Observed preference across multiple apps"
        )
        
        contexts = [
            DecisionContext(base_prop, 0.8, "vscode", 5.0),
            DecisionContext(base_prop, 0.8, "vscode", 5.0),  # Identical
            DecisionContext(base_prop, 0.8, "vscode", 5.0),  # Identical
        ]
        
        decisions = []
        for context in contexts:
            decision, metadata = self.engine.make_decision(context)
            decisions.append(decision)
        
        # All decisions should be identical
        if len(set(decisions)) == 1:
            print(f"✅ Consistent decisions: {decisions[0]}")
            return True
        else:
            print(f"❌ INCONSISTENT decisions: {decisions}")
            return False
    
    def test_attention_sensitivity(self) -> bool:
        """
        TEST 2: Attention Sensitivity  
        Does attention level actually affect decisions?
        """
        print("🧪 TEST 2: Attention Sensitivity")
        
        prop = Proposition(text="User might like jazz music", confidence=5, reasoning="Limited evidence")
        
        # Test extreme attention levels
        high_focus = DecisionContext(prop, 0.95, "xcode", 2.0)
        low_focus = DecisionContext(prop, 0.05, "spotify", 300.0)
        
        high_decision, high_meta = self.engine.make_decision(high_focus)
        low_decision, low_meta = self.engine.make_decision(low_focus)
        
        print(f"High focus: {high_decision} (EU: {high_meta['expected_utilities']})")
        print(f"Low focus: {low_decision} (EU: {low_meta['expected_utilities']})")
        
        # High focus should be more conservative (lower utility for interruptions)
        high_interrupt_penalty = high_meta['utilities_used']['u_action_goal_false']
        low_interrupt_penalty = low_meta['utilities_used']['u_action_goal_false']
        
        if high_interrupt_penalty < low_interrupt_penalty:  # More negative = higher penalty
            print("✅ Attention sensitivity working")
            return True
        else:
            print(f"❌ No attention sensitivity: high={high_interrupt_penalty}, low={low_interrupt_penalty}")
            return False
    
    def test_confidence_thresholds(self) -> bool:
        """
        TEST 3: Confidence Thresholds
        Do different confidence levels lead to meaningful decision changes?
        """
        print("🧪 TEST 3: Confidence Thresholds")
        
        confidence_levels = [1, 3, 5, 7, 9]
        decisions_by_confidence = {}
        
        for conf in confidence_levels:
            prop = Proposition(text="Test proposition", confidence=conf, reasoning="Test")
            context = DecisionContext(prop, 0.5, "safari", 10.0)  # Neutral context
            
            decision, metadata = self.engine.make_decision(context)
            decisions_by_confidence[conf] = decision
        
        print(f"Decisions by confidence: {decisions_by_confidence}")
        
        # Check for reasonable patterns
        unique_decisions = len(set(decisions_by_confidence.values()))
        if unique_decisions >= 2:
            print(f"✅ Confidence affects decisions ({unique_decisions} unique)")
            return True
        else:
            print("❌ Confidence doesn't affect decisions")
            return False
    
    def test_app_classification_impact(self) -> bool:
        """
        TEST 4: App Classification Impact
        Does app type actually affect focus calculation?
        """
        print("🧪 TEST 4: App Classification Impact")
        
        # Test known focus vs casual apps
        focus_apps = ["xcode", "vscode", "terminal"]
        casual_apps = ["safari", "spotify", "instagram"]
        
        prop = Proposition(text="Test", confidence=5, reasoning="Test")
        
        focus_decisions = []
        casual_decisions = []
        
        for app in focus_apps:
            context = DecisionContext(prop, 0.7, app, 10.0)
            decision, _ = self.engine.make_decision(context)
            focus_decisions.append(decision)
        
        for app in casual_apps:
            context = DecisionContext(prop, 0.7, app, 10.0)
            decision, _ = self.engine.make_decision(context)
            casual_decisions.append(decision)
        
        print(f"Focus app decisions: {focus_decisions}")
        print(f"Casual app decisions: {casual_decisions}")
        
        # Focus apps should lead to more conservative decisions
        conservativeness = {"no_action": 0, "dialogue": 1, "autonomous_action": 2}
        
        focus_conservativeness = statistics.mean([conservativeness[d] for d in focus_decisions])
        casual_conservativeness = statistics.mean([conservativeness[d] for d in casual_decisions])
        
        if focus_conservativeness <= casual_conservativeness:
            print("✅ App classification affects decisions")
            return True
        else:
            print(f"❌ No app impact: focus={focus_conservativeness}, casual={casual_conservativeness}")
            return False
    
    def test_attention_calculation_realism(self) -> bool:
        """
        TEST 5: Attention Calculation Realism
        Does the attention monitor produce realistic focus values?
        """
        print("🧪 TEST 5: Attention Calculation Realism")
        
        # Test various realistic scenarios
        test_cases = [
            ("coding", "vscode", 0, 5),      # Should be high focus
            ("browsing", "safari", 180, 0),  # Should be low focus  
            ("idle", "unknown", 600, 0),     # Should be very low focus
        ]
        
        focus_values = []
        
        for scenario, app, idle_time, activity in test_cases:
            # Simulate attention state
            self.attention_monitor.last_activity_time = time.time() - idle_time
            
            # Calculate focus (would need to mock some internals for full test)
            # For now, test the classification function
            app_focus = self.attention_monitor.classify_app_focus_level(app)
            focus_values.append((scenario, app_focus))
            print(f"{scenario}: app_focus={app_focus}")
        
        # Check that focus values are reasonable
        coding_focus = focus_values[0][1]
        browsing_focus = focus_values[1][1] 
        unknown_focus = focus_values[2][1]
        
        if coding_focus > browsing_focus > unknown_focus:
            print("✅ Attention calculation is reasonable")
            return True
        else:
            print(f"❌ Unrealistic attention: coding={coding_focus}, browsing={browsing_focus}, unknown={unknown_focus}")
            return False
    
    def test_performance_under_load(self) -> bool:
        """
        TEST 6: Performance Under Load
        Can the system handle realistic decision volume?
        """
        print("🧪 TEST 6: Performance Under Load")
        
        # Simulate 100 decisions (realistic for active user)
        start_time = time.time()
        
        for i in range(100):
            prop = Proposition(text=f"Proposition {i}", confidence=i%10+1, reasoning="Test")
            context = DecisionContext(prop, 0.5, "test", 10.0)
            
            decision, metadata = self.engine.make_decision(context)
            # Should not throw exceptions
        
        elapsed = time.time() - start_time
        decisions_per_second = 100 / elapsed
        
        print(f"Performance: {decisions_per_second:.1f} decisions/sec")
        
        if decisions_per_second > 10:  # Should handle at least 10 decisions per second
            print("✅ Performance acceptable")
            return True
        else:
            print("❌ Performance too slow")
            return False
    
    def test_edge_cases(self) -> bool:
        """
        TEST 7: Edge Cases
        Does the system handle edge cases gracefully?
        """
        print("🧪 TEST 7: Edge Cases")
        
        edge_cases = [
            # None/invalid values
            DecisionContext(None, 0.5, "test", 10.0),
            
            # Extreme values
            DecisionContext(
                Proposition(text="", confidence=0, reasoning=""),  # Empty proposition
                -1.0,  # Invalid attention
                "",    # Empty app
                -100   # Negative idle time
            ),
            
            # Very long text
            DecisionContext(
                Proposition(text="x" * 10000, confidence=5, reasoning="x" * 1000),
                1.5,   # Out of range attention
                "app" * 100,  # Very long app name
                999999  # Extreme idle time
            )
        ]
        
        failures = 0
        for i, context in enumerate(edge_cases):
            try:
                decision, metadata = self.engine.make_decision(context)
                print(f"Edge case {i+1}: {decision} (handled gracefully)")
            except Exception as e:
                print(f"Edge case {i+1}: FAILED with {e}")
                failures += 1
        
        if failures == 0:
            print("✅ All edge cases handled")
            return True
        else:
            print(f"❌ {failures} edge cases failed")
            return False
    
    def run_all_tests(self) -> Dict[str, bool]:
        """Run all functionality tests."""
        print("🔥 REAL FUNCTIONALITY TESTS")
        print("=" * 60)
        
        tests = [
            ("Decision Consistency", self.test_decision_consistency),
            ("Attention Sensitivity", self.test_attention_sensitivity), 
            ("Confidence Thresholds", self.test_confidence_thresholds),
            ("App Classification", self.test_app_classification_impact),
            ("Attention Realism", self.test_attention_calculation_realism),
            ("Performance Load", self.test_performance_under_load),
            ("Edge Cases", self.test_edge_cases),
        ]
        
        results = {}
        passed = 0
        
        for test_name, test_func in tests:
            print(f"\n--- {test_name} ---")
            try:
                success = test_func()
                results[test_name] = success
                if success:
                    passed += 1
            except Exception as e:
                print(f"❌ {test_name} CRASHED: {e}")
                results[test_name] = False
        
        print("\n" + "=" * 60)
        print(f"📊 RESULTS: {passed}/{len(tests)} tests passed")
        
        if passed == len(tests):
            print("🎉 ALL TESTS PASSED - System might actually work!")
        elif passed >= len(tests) * 0.7:
            print("⚠️  MOSTLY WORKING - Some issues to fix")
        else:
            print("💥 SYSTEM IS BROKEN - Major fixes needed")
        
        return results

def main():
    """Run the real functionality tests."""
    tester = RealFunctionalityTester()
    results = tester.run_all_tests()
    
    # Print detailed analysis
    print("\n🔍 DETAILED ANALYSIS:")
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {test_name}")
    
    # Return exit code based on results
    success_rate = sum(results.values()) / len(results)
    if success_rate >= 0.8:
        print("\n🎯 System is functional enough for basic use")
        exit(0)
    else:
        print(f"\n💀 System has serious issues (success rate: {success_rate:.1%})")
        exit(1)

if __name__ == "__main__":
    main()
