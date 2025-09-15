"""
Unit tests for the Mixed-Initiative Decision Engine
"""

import pytest
from gum.decision import MixedInitiativeDecisionEngine, DecisionContext
from gum.models import Proposition

def test_attention_aware_behavior():
    """Test that attention level properly affects decisions."""
    engine = MixedInitiativeDecisionEngine(debug=False)
    
    # Very low confidence proposition  
    low_conf_prop = Proposition(
        text="User might prefer dark mode",
        confidence=2,  # Very low confidence  
        reasoning="Almost no evidence"
    )
    
    # High focus context - should prefer no_action
    high_focus_context = DecisionContext(
        proposition=low_conf_prop,
        user_attention_level=0.9,
        active_application="Xcode"
    )
    
    # Low focus context - should prefer dialogue  
    low_focus_context = DecisionContext(
        proposition=low_conf_prop,
        user_attention_level=0.2,
        active_application="Safari"
    )
    
    high_focus_decision, _ = engine.make_decision(high_focus_context)
    low_focus_decision, _ = engine.make_decision(low_focus_context)
    
    # High focus should be more conservative (no_action)
    # Low focus should be more liberal (dialogue)
    assert high_focus_decision == "no_action", f"Expected no_action for high focus, got {high_focus_decision}"
    assert low_focus_decision == "dialogue", f"Expected dialogue for low focus, got {low_focus_decision}"
    
    print("✅ Attention-aware behavior test passed!")

def test_confidence_thresholds():
    """Test that confidence levels produce expected decisions."""
    engine = MixedInitiativeDecisionEngine(debug=False)
    
    # High confidence should lead to action
    high_conf_prop = Proposition(text="User prefers Python", confidence=9, reasoning="Strong evidence")
    high_conf_context = DecisionContext(proposition=high_conf_prop, user_attention_level=0.5)
    
    # Very low confidence should lead to no action
    very_low_conf_prop = Proposition(text="User might like jazz", confidence=1, reasoning="No evidence")
    very_low_conf_context = DecisionContext(proposition=very_low_conf_prop, user_attention_level=0.5)
    
    high_conf_decision, _ = engine.make_decision(high_conf_context)
    very_low_conf_decision, _ = engine.make_decision(very_low_conf_context)
    
    assert high_conf_decision == "autonomous_action", f"Expected autonomous_action for high confidence, got {high_conf_decision}"
    assert very_low_conf_decision == "no_action", f"Expected no_action for very low confidence, got {very_low_conf_decision}"
    
    print("✅ Confidence threshold test passed!")

if __name__ == "__main__":
    test_attention_aware_behavior()
    test_confidence_thresholds()
    print("\n🎉 All decision engine tests passed!")
