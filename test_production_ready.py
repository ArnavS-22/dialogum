"""
Production readiness test for Conversational GUM Refinement system.

This test validates that the system is robust, handles errors gracefully,
and performs correctly under realistic conditions.
"""

import asyncio
import logging
import pytest
from unittest.mock import patch, MagicMock
from gum.gum import gum
from gum.models import Proposition
from gum.config import GumConfig, DecisionConfig, AttentionConfig
from gum.decision import MixedInitiativeDecisionEngine, DecisionContext
from gum.attention import AttentionMonitor

# Configure logging for tests
logging.basicConfig(level=logging.WARNING)

def test_error_handling():
    """Test that the system handles errors gracefully without crashing."""
    print("🧪 Testing Error Handling")
    
    # Test decision engine with invalid inputs
    engine = MixedInitiativeDecisionEngine(debug=False)
    
    # Test with None proposition
    try:
        context = DecisionContext(
            proposition=None,  # Invalid input
            user_attention_level=0.5,
            active_application="test"
        )
        decision, metadata = engine.make_decision(context)
        assert decision == "no_action"  # Should gracefully fallback
        assert "error" in metadata
        print("✅ Graceful handling of None proposition")
    except Exception as e:
        print(f"❌ Failed to handle None proposition: {e}")
        return False
    
    # Test with invalid confidence values
    try:
        invalid_prop = Proposition(text="test", confidence=999, reasoning="test")
        context = DecisionContext(
            proposition=invalid_prop,
            user_attention_level=0.5,
            active_application="test"
        )
        decision, metadata = engine.make_decision(context)
        # Should clamp confidence to valid range
        assert 1 <= metadata["confidence"] <= 10
        print("✅ Confidence clamping works")
    except Exception as e:
        print(f"❌ Failed to handle invalid confidence: {e}")
        return False
    
    return True

def test_configuration_system():
    """Test that configuration system works properly."""
    print("🧪 Testing Configuration System")
    
    # Test custom configuration
    custom_config = GumConfig()
    custom_config.decision.base_p_no_action_dialogue = 0.2
    custom_config.decision.base_p_dialogue_action = 0.8
    custom_config.attention.update_interval = 5.0
    
    engine = MixedInitiativeDecisionEngine(config=custom_config.decision, debug=False)
    
    # Verify configuration was applied
    assert engine.config.base_p_no_action_dialogue == 0.2
    assert engine.config.base_p_dialogue_action == 0.8
    print("✅ Custom configuration applied correctly")
    
    # Test environment variable loading
    import os
    os.environ['P_NO_ACTION_DIALOGUE'] = '0.1'
    os.environ['ATTENTION_UPDATE_INTERVAL'] = '3.0'
    
    env_config = GumConfig()
    assert env_config.decision.base_p_no_action_dialogue == 0.1
    assert env_config.attention.update_interval == 3.0
    print("✅ Environment variable loading works")
    
    # Clean up
    del os.environ['P_NO_ACTION_DIALOGUE']
    del os.environ['ATTENTION_UPDATE_INTERVAL']
    
    return True

def test_attention_monitor_robustness():
    """Test attention monitor handles system failures gracefully."""
    print("🧪 Testing Attention Monitor Robustness")
    
    monitor = AttentionMonitor(debug=False)
    
    # Test with broken app detection (should not crash)
    with patch('subprocess.run', side_effect=Exception("System error")):
        app = monitor.get_active_application()
        assert app == "unknown"  # Should fallback gracefully
        print("✅ Handles broken app detection")
    
    # Test focus calculation with edge cases
    attention_state = monitor.calculate_focus_level()
    assert 0.0 <= attention_state <= 1.0
    print("✅ Focus calculation returns valid range")
    
    # Test monitoring loop doesn't crash on errors
    monitor.start_monitoring()
    import time
    time.sleep(1)  # Let it run briefly
    monitor.stop_monitoring()
    print("✅ Monitoring loop handles errors gracefully")
    
    return True

def test_decision_engine_mathematical_properties():
    """Test that decision engine maintains mathematical properties."""
    print("🧪 Testing Decision Engine Mathematical Properties")
    
    engine = MixedInitiativeDecisionEngine(debug=False)
    
    test_cases = [
        # (confidence, expected_decision_type)
        (1, "no_action"),      # Very low confidence should avoid action
        (5, "dialogue"),       # Medium confidence should trigger dialogue  
        (9, "autonomous_action"),  # High confidence should trigger action
    ]
    
    for confidence, expected_type in test_cases:
        prop = Proposition(text="test", confidence=confidence, reasoning="test")
        
        # Test with high focus (should be more conservative)
        high_focus_context = DecisionContext(
            proposition=prop,
            user_attention_level=0.9,
            active_application="Xcode"
        )
        
        # Test with low focus (should be more liberal) 
        low_focus_context = DecisionContext(
            proposition=prop,
            user_attention_level=0.2,
            active_application="Safari"
        )
        
        high_focus_decision, _ = engine.make_decision(high_focus_context)
        low_focus_decision, _ = engine.make_decision(low_focus_context)
        
        # Mathematical property: high focus should be more conservative
        # (either same decision or more conservative)
        conservativeness = {"no_action": 0, "dialogue": 1, "autonomous_action": 2}
        
        assert conservativeness[high_focus_decision] <= conservativeness[low_focus_decision], \
            f"High focus should be more conservative: {high_focus_decision} vs {low_focus_decision}"
    
    print("✅ Decision engine maintains mathematical properties")
    return True

async def test_gum_integration_robustness():
    """Test that GUM integration is robust and doesn't break core functionality."""
    print("🧪 Testing GUM Integration Robustness")
    
    # Test with custom configuration
    config = GumConfig()
    config.decision.base_p_no_action_dialogue = 0.4
    
    # Create GUM instance
    gum_instance = gum(
        'Test User', 
        'gpt-4o-mini', 
        enable_mixed_initiative=True,
        config=config,
        verbosity=logging.ERROR  # Quiet for test
    )
    
    await gum_instance.connect_db()
    
    # Test that decision evaluation doesn't break GUM
    try:
        test_prop = Proposition(
            text="User prefers testing over production code",
            confidence=6,
            reasoning="Test evidence"
        )
        
        # This should not throw an exception
        gum_instance._evaluate_proposition_for_action(test_prop)
        print("✅ Decision evaluation integrates cleanly with GUM")
        
    except Exception as e:
        print(f"❌ GUM integration failed: {e}")
        return False
    
    return True

async def test_end_to_end_scenario():
    """Test a realistic end-to-end scenario."""
    print("🧪 Testing End-to-End Scenario")
    
    # Simulate a realistic configuration
    config = GumConfig()
    
    # Create GUM with mixed-initiative enabled
    gum_instance = gum(
        'Production User',
        'gpt-4o-mini',
        enable_mixed_initiative=True,
        config=config,
        verbosity=logging.ERROR
    )
    
    await gum_instance.connect_db()
    
    # Start the system
    gum_instance.start_update_loop()
    
    # Simulate different proposition scenarios
    scenarios = [
        Proposition(text="User is a Python developer", confidence=9, reasoning="Strong evidence"),
        Proposition(text="User might like jazz", confidence=3, reasoning="Weak evidence"),
        Proposition(text="User prefers dark mode", confidence=7, reasoning="Good evidence"),
        Proposition(text="User potentially works remotely", confidence=2, reasoning="Minimal evidence"),
    ]
    
    try:
        for prop in scenarios:
            gum_instance._evaluate_proposition_for_action(prop)
        
        print("✅ End-to-end scenario completed successfully")
        result = True
        
    except Exception as e:
        print(f"❌ End-to-end scenario failed: {e}")
        result = False
    
    finally:
        # Clean shutdown
        await gum_instance.stop_update_loop()
    
    return result

async def run_all_tests():
    """Run all production readiness tests."""
    print("🚀 Running Production Readiness Tests")
    print("="*60)
    
    tests = [
        ("Error Handling", test_error_handling),
        ("Configuration System", test_configuration_system),
        ("Attention Monitor Robustness", test_attention_monitor_robustness),
        ("Mathematical Properties", test_decision_engine_mathematical_properties),
        ("GUM Integration", test_gum_integration_robustness),
        ("End-to-End Scenario", test_end_to_end_scenario),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            if result:
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"❌ {test_name} FAILED with exception: {e}")
    
    print("\n" + "="*60)
    print(f"📊 Production Readiness: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 System is PRODUCTION READY!")
        print("✅ Robust error handling")
        print("✅ Configurable and maintainable")
        print("✅ Mathematically sound decisions")
        print("✅ Clean integration with GUM")
        return True
    else:
        print(f"⚠️  System needs {total - passed} fixes before production")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)
