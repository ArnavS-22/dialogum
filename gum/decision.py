"""
Mixed-Initiative Decision Engine for Conversational GUM Refinement

Implements the core decision logic from Horvitz's "Principles of Mixed-Initiative User Interfaces"
with attention-aware threshold adjustment.
"""

import logging
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from .models import Proposition
from .config import DecisionConfig

logger = logging.getLogger(__name__)

@dataclass
class DecisionContext:
    """Context information for making mixed-initiative decisions."""
    proposition: Proposition
    user_attention_level: float = 0.5  # 0.0 = idle, 1.0 = highly focused
    active_application: str = "unknown"
    idle_time_seconds: float = 0.0
    
class MixedInitiativeDecisionEngine:
    """
    Core decision engine that determines whether to:
    1. Take no action (accept proposition quietly)
    2. Take autonomous action (show suggestion)  
    3. Initiate dialogue (ask GATE question)
    
    Based on Horvitz's expected utility framework with attention-aware adjustments.
    """
    
    def __init__(self, 
                 config: Optional[DecisionConfig] = None,
                 debug: bool = False):
        """
        Initialize decision engine with configuration.
        
        Args:
            config: DecisionConfig object with thresholds and utilities
            debug: Enable debug logging
        """
        self.config = config or DecisionConfig()
        self.debug = debug
        
        # Load utilities from config
        self.base_utilities = {
            "u_action_goal_true": self.config.u_action_goal_true,
            "u_action_goal_false": self.config.u_action_goal_false,  
            "u_no_action_goal_true": self.config.u_no_action_goal_true,
            "u_no_action_goal_false": self.config.u_no_action_goal_false,
            "u_dialogue_goal_true": self.config.u_dialogue_goal_true,
            "u_dialogue_goal_false": self.config.u_dialogue_goal_false
        }
        
        if self.debug:
            logger.info(f"Initialized MixedInitiativeDecisionEngine with base thresholds: "
                       f"p_no_action={self.config.base_p_no_action_dialogue}, "
                       f"p_action={self.config.base_p_dialogue_action}")
    
    def adjust_utilities_for_attention(self, attention_level: float, active_app: str) -> Dict[str, float]:
        """
        Adjust utilities based on user's current attention state.
        
        This is the core novelty: dynamically adjusting intervention costs based on attention.
        
        Args:
            attention_level: 0.0 (idle) to 1.0 (highly focused)
            active_app: Name of currently active application
            
        Returns:
            Dictionary of adjusted utilities
        """
        utilities = self.base_utilities.copy()
        
        # High focus applications get extra focus boost
        focus_apps = {"xcode", "vscode", "terminal", "intellij", "pycharm", "sublime"}
        if active_app.lower() in focus_apps:
            attention_level = min(1.0, attention_level + 0.2)
        
        # Attention-aware adjustment of interruption cost (THE KEY NOVELTY)
        if attention_level > self.config.high_focus_threshold:  # Highly focused
            # Much higher cost to interrupt when user is focused
            base_action_cost = self.config.u_action_goal_false
            base_dialogue_cost = self.config.u_dialogue_goal_false
            utilities["u_action_goal_false"] = base_action_cost * self.config.high_focus_penalty_multiplier
            utilities["u_dialogue_goal_false"] = base_dialogue_cost * self.config.high_focus_penalty_multiplier
            if self.debug:
                logger.info(f"High focus detected ({attention_level:.2f}) - raising interruption costs significantly")
                
        elif attention_level < self.config.low_focus_threshold:  # Idle/browsing
            # Lower cost to interrupt when user is idle  
            base_action_cost = self.config.u_action_goal_false
            base_dialogue_cost = self.config.u_dialogue_goal_false
            utilities["u_action_goal_false"] = base_action_cost * self.config.low_focus_penalty_reduction
            utilities["u_dialogue_goal_false"] = base_dialogue_cost * self.config.low_focus_penalty_reduction
            if self.debug:
                logger.info(f"Low focus detected ({attention_level:.2f}) - lowering interruption costs")
        
        return utilities
    
    def calculate_expected_utilities(self, p_goal: float, utilities: Dict[str, float]) -> Tuple[float, float, float]:
        """
        Calculate expected utilities for the three possible actions.
        
        Uses exact formulas from Horvitz paper:
        eu(A|E) = p(G|E) * u(A,G) + [1-p(G|E)] * u(A,¬G)
        
        Args:
            p_goal: Probability that user has the goal (confidence/10.0)
            utilities: Utility values for different outcomes
            
        Returns:
            Tuple of (eu_no_action, eu_dialogue, eu_action)
        """
        p_no_goal = 1.0 - p_goal
        
        # Expected utility of taking no action
        eu_no_action = (p_goal * utilities["u_no_action_goal_true"] + 
                       p_no_goal * utilities["u_no_action_goal_false"])
        
        # Expected utility of autonomous action
        eu_action = (p_goal * utilities["u_action_goal_true"] + 
                    p_no_goal * utilities["u_action_goal_false"])
        
        # Expected utility of dialogue
        eu_dialogue = (p_goal * utilities["u_dialogue_goal_true"] + 
                      p_no_goal * utilities["u_dialogue_goal_false"])
        
        return eu_no_action, eu_dialogue, eu_action
    
    def make_decision(self, context: DecisionContext) -> Tuple[str, Dict]:
        """
        Make the core mixed-initiative decision.
        
        Args:
            context: DecisionContext with proposition and attention info
            
        Returns:
            Tuple of (decision, metadata) where decision is one of:
            - "no_action": Accept proposition quietly
            - "dialogue": Initiate GATE dialogue  
            - "autonomous_action": Show suggestion/take action
        """
        try:
            # Convert confidence to probability (0-1 scale)
            confidence = context.proposition.confidence or 5  # Default if None
            confidence = max(1, min(10, confidence))  # Clamp to valid range
            p_goal = confidence / 10.0
            
            # Adjust utilities based on attention
            utilities = self.adjust_utilities_for_attention(
                context.user_attention_level, 
                context.active_application
            )
            
            # Calculate expected utilities
            eu_no_action, eu_dialogue, eu_action = self.calculate_expected_utilities(p_goal, utilities)
            
            # Determine best action (highest expected utility)
            utilities_dict = {
                "no_action": eu_no_action,
                "dialogue": eu_dialogue, 
                "autonomous_action": eu_action
            }
            
            best_action = max(utilities_dict.keys(), key=lambda x: utilities_dict[x])
            
            # Metadata for debugging/logging
            metadata = {
                "confidence": confidence,
                "p_goal": p_goal,
                "attention_level": context.user_attention_level,
                "active_app": context.active_application,
                "expected_utilities": utilities_dict,
                "utilities_used": utilities,
                "proposition_text": context.proposition.text
            }
            
            if self.debug:
                logger.info(f"Decision: {best_action} (EU: {utilities_dict[best_action]:.3f}) "
                           f"for proposition: '{context.proposition.text[:50]}...'")
            
            return best_action, metadata
            
        except Exception as e:
            logger.error(f"Error in decision engine: {e}")
            # Graceful fallback - default to no action
            return "no_action", {
                "error": str(e),
                "confidence": getattr(context.proposition, 'confidence', 0),
                "attention_level": context.user_attention_level,
                "active_app": context.active_application,
                "proposition_text": getattr(context.proposition, 'text', 'unknown')
            }


def test_decision_engine():
    """Test the decision engine with various scenarios."""
    print("🧪 Testing Mixed-Initiative Decision Engine")
    
    engine = MixedInitiativeDecisionEngine(debug=True)
    
    # Test proposition with high confidence
    from .models import Proposition
    high_conf_prop = Proposition(
        text="User prefers Python over Java for web development",
        confidence=9,
        reasoning="User consistently chooses Python frameworks"
    )
    
    # Test scenarios
    scenarios = [
        # High confidence, high focus -> should not interrupt
        DecisionContext(high_conf_prop, user_attention_level=0.9, active_application="Xcode"),
        
        # High confidence, low focus -> might take action
        DecisionContext(high_conf_prop, user_attention_level=0.2, active_application="Safari"),
        
        # Low confidence, high focus -> definitely no action
        DecisionContext(
            Proposition(text="User might like jazz music", confidence=3, reasoning="Limited evidence"),
            user_attention_level=0.9, 
            active_application="VSCode"
        ),
        
        # Low confidence, low focus -> might ask question
        DecisionContext(
            Proposition(text="User might like jazz music", confidence=3, reasoning="Limited evidence"),
            user_attention_level=0.2,
            active_application="Spotify"
        ),
    ]
    
    for i, context in enumerate(scenarios):
        print(f"\n--- Scenario {i+1} ---")
        print(f"Proposition: {context.proposition.text}")
        print(f"Confidence: {context.proposition.confidence}/10")
        print(f"Attention: {context.user_attention_level:.1f}, App: {context.active_application}")
        
        decision, metadata = engine.make_decision(context)
        print(f"Decision: {decision}")
        print(f"Expected Utilities: {metadata['expected_utilities']}")
    
    print("\n✅ Decision engine test completed!")

if __name__ == "__main__":
    test_decision_engine()
