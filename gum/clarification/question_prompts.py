"""
Prompt templates and few-shot examples for clarifying question generation.

This module provides:
- Few-shot examples for factors 3, 6, 8, 11
- Controlled QG prompt templates
- Functions to build prompts dynamically
"""

from typing import Dict, List, Any
from .question_config import get_factor_description


# Few-shot examples for factors that use this method
FEW_SHOT_EXAMPLES: Dict[int, List[Dict[str, Any]]] = {
    3: [  # Inferred Intent
        {
            "prop": "You value communication with friends and professional contacts, as evidenced by multiple messaging sessions.",
            "question": "When you messaged those contacts, was it mostly to coordinate plans or to socialize?",
            "reasoning": "This proposition infers motive from messaging patterns; clarifying confirms the actual intent.",
            "evidence": ["obs_451: multiple WhatsApp Web sessions on 2025-09-29", "obs_452: opened chat with 3 different contacts"]
        },
        {
            "prop": "You are interested in improving documentation quality based on repeated editing of README files.",
            "question": "When you edited those README files, were you improving documentation or working on something else?",
            "reasoning": "This assumes motivation from file edits; asking confirms whether documentation was the actual goal.",
            "evidence": ["obs_203: edited README.md multiple times", "obs_204: opened documentation folder"]
        },
        {
            "prop": "You prioritize learning new technologies, as shown by browsing technical documentation sites.",
            "question": "When you browsed those technical sites, were you learning something new or troubleshooting a specific problem?",
            "reasoning": "This infers learning intent from browsing; clarifying distinguishes between learning and problem-solving.",
            "evidence": ["obs_312: visited React documentation", "obs_313: browsed Python tutorials"]
        }
    ],
    6: [  # Opacity
        {
            "prop": "You may undervalue less quantifiable aspects of software development.",
            "question": "Could you clarify what 'less quantifiable aspects' means in this context?",
            "reasoning": "The phrase is abstract; clarifying grounds the claim in specific examples.",
            "evidence": []
        },
        {
            "prop": "You demonstrate a preference for structured thinking in your work approach.",
            "question": "What specific behaviors in your work approach would you say reflect structured thinking?",
            "reasoning": "The claim is vague about evidence; asking identifies concrete examples from your experience.",
            "evidence": []
        },
        {
            "prop": "You show signs of being detail-oriented in technical contexts.",
            "question": "Could you provide examples of when you've been detail-oriented in your technical work?",
            "reasoning": "The assessment lacks clear supporting evidence; clarifying requests specific instances from your experience.",
            "evidence": []
        }
    ],
    8: [  # Privacy
        {
            "prop": "You are editing a document titled 'Personal Health Goals 2025' with specific medical information.",
            "question": "Would you prefer to discuss this more privately, or is this detail level okay?",
            "reasoning": "This touches sensitive health domains; asking checks consent level.",
            "evidence": ["obs_176: editing document with health information"]
        },
        {
            "prop": "You have been reviewing financial statements and bank account details in multiple spreadsheets.",
            "question": "Would you prefer we keep this level of financial detail in observations, or generalize it?",
            "reasoning": "Financial information is sensitive; asking confirms appropriate privacy boundaries.",
            "evidence": ["obs_289: opened banking spreadsheet", "obs_290: reviewed account balances"]
        },
        {
            "prop": "You had a conversation with a therapist about relationship difficulties, as captured in calendar events.",
            "question": "This touches on personal matters. Would you like us to exclude this type of information from observations?",
            "reasoning": "Relationship and therapy contexts are highly sensitive; asking respects privacy preferences.",
            "evidence": ["obs_401: calendar event with therapist", "obs_402: relationship discussion notes"]
        }
    ],
    11: [  # Ambiguity
        {
            "prop": "You are focused on development work throughout the day.",
            "question": "When you say 'focused on development', do you mean coding tasks, project planning, or learning new skills?",
            "reasoning": "The term 'development' has multiple interpretations; clarifying specifies which meaning applies.",
            "evidence": []
        },
        {
            "prop": "You frequently engage with tools and systems to improve productivity.",
            "question": "What does 'engaging with tools' refer to for you—using specific software, configuring settings, or something else?",
            "reasoning": "The phrase is ambiguous about what actions constitute engagement; asking clarifies the referent.",
            "evidence": []
        },
        {
            "prop": "You show interest in optimization across multiple contexts.",
            "question": "Does 'optimization' here mean performance improvements, workflow efficiency, or code quality?",
            "reasoning": "The term has multiple technical meanings; clarifying distinguishes which type of optimization is relevant.",
            "evidence": []
        }
    ]
}


# Controlled QG system prompt template
CONTROLLED_QG_SYSTEM_PROMPT = """You are generating a clarifying question for a flagged proposition.

The proposition is a statement the SYSTEM made about the user, not something the user said.

IMPORTANT: Ask the user directly about THE CLAIM IN THE PROPOSITION, not about how the system determined it.
- DO NOT ask about "how the system determined" or "the system's observation"
- DO NOT reference "the system" in your question
- DO ask the user to confirm, clarify, or correct THE ACTUAL CLAIM

Guidelines:
- Ask ONE neutral, clarifying question directed at the user as "you"
- Always address the user as "you" - if the proposition mentions a name, convert it to "you"/"your"
- Use polite, non-judgmental language
- Avoid assumptive phrasing ("didn't you", "since you", "you always")
- Prefer "could", "would", "might", "perhaps" for politeness
- Do not make multiple asks in one question
- Be specific but respectful
- Ask about the actual claim/behavior, not about the system's method or process

Factor: {factor_description}
Proposition: {proposition_text}
Observations: {observation_summary}

Generate a clarifying question and a brief reasoning (≤30 words) explaining why you asked.
"""


# Controlled QG user prompt
CONTROLLED_QG_USER_PROMPT = """Return JSON with exactly this structure:
{{
    "question": "your clarifying question here",
    "reasoning": "your brief reasoning here (≤30 words)"
}}"""


# Few-shot system prompt template
FEW_SHOT_SYSTEM_PROMPT = """You are generating a clarifying question for a flagged proposition.

The proposition is a statement the SYSTEM made about the user, not something the user said.

IMPORTANT: Ask the user directly about THE CLAIM IN THE PROPOSITION, not about how the system determined it.
- Always address the user as "you" - if the proposition mentions a name, convert it to "you"/"your"
- DO NOT ask about "how the system determined" or "the system's observation"
- DO NOT reference "the system" in your question
- DO ask the user to confirm, clarify, or correct THE ACTUAL CLAIM

Below are examples of good clarifying questions for similar cases:

{examples}

Now generate a similar clarifying question for the following:

Factor: {factor_description}
Proposition: {proposition_text}
Observations: {observation_summary}

Generate a clarifying question and a brief reasoning (≤30 words) explaining why you asked.
Follow the pattern shown in the examples above.
"""


# Few-shot user prompt
FEW_SHOT_USER_PROMPT = """Return JSON with exactly this structure:
{{
    "question": "your clarifying question here",
    "reasoning": "your brief reasoning here (≤30 words)"
}}"""


def get_few_shot_examples(factor_id: int) -> List[Dict[str, Any]]:
    """
    Get few-shot examples for a factor.
    
    Args:
        factor_id: The factor ID
        
    Returns:
        List of example dicts with 'prop', 'question', 'reasoning', 'evidence'
        
    Raises:
        ValueError: If factor doesn't use few-shot method
    """
    if factor_id not in FEW_SHOT_EXAMPLES:
        raise ValueError(f"Factor {factor_id} does not use few-shot method")
    return FEW_SHOT_EXAMPLES[factor_id]


def format_few_shot_examples(factor_id: int) -> str:
    """
    Format few-shot examples as a string for prompt inclusion.
    
    Args:
        factor_id: The factor ID
        
    Returns:
        Formatted examples string
    """
    examples = get_few_shot_examples(factor_id)
    formatted = []
    
    for i, ex in enumerate(examples, 1):
        example_text = f"""Example {i}:
Proposition: "{ex['prop']}"
Question: "{ex['question']}"
Reasoning: "{ex['reasoning']}"
"""
        if ex.get('evidence'):
            evidence_str = ", ".join(ex['evidence'])
            example_text += f"Evidence: [{evidence_str}]\n"
        formatted.append(example_text)
    
    return "\n".join(formatted)


def build_few_shot_prompt(
    prop_text: str,
    factor_id: int,
    observation_summary: str
) -> tuple[str, str]:
    """
    Build few-shot prompt (system + user).
    
    Args:
        prop_text: The proposition text
        factor_id: The factor ID
        observation_summary: Summary of observations
        
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    factor_description = get_factor_description(factor_id)
    examples = format_few_shot_examples(factor_id)
    
    # Normalize proposition text to use "you" instead of names
    normalized_prop = normalize_proposition_for_prompt(prop_text)
    
    system_prompt = FEW_SHOT_SYSTEM_PROMPT.format(
        examples=examples,
        factor_description=factor_description,
        proposition_text=normalized_prop,
        observation_summary=observation_summary
    )
    
    return system_prompt, FEW_SHOT_USER_PROMPT


def build_controlled_qg_prompt(
    prop_text: str,
    factor_id: int,
    observation_summary: str,
    validation_feedback: str = ""
) -> tuple[str, str]:
    """
    Build controlled QG prompt (system + user).
    
    Args:
        prop_text: The proposition text
        factor_id: The factor ID
        observation_summary: Summary of observations
        validation_feedback: Optional feedback from previous validation failure
        
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    factor_description = get_factor_description(factor_id)
    
    # Normalize proposition text to use "you" instead of names
    normalized_prop = normalize_proposition_for_prompt(prop_text)
    
    system_prompt = CONTROLLED_QG_SYSTEM_PROMPT.format(
        factor_description=factor_description,
        proposition_text=normalized_prop,
        observation_summary=observation_summary
    )
    
    # Add validation feedback if retrying
    if validation_feedback:
        system_prompt += f"\n\nPrevious attempt failed validation: {validation_feedback}\nPlease correct these issues."
    
    return system_prompt, CONTROLLED_QG_USER_PROMPT


def normalize_proposition_for_prompt(prop_text: str) -> str:
    """
    Normalize proposition text for prompts - convert names to "you".
    
    This helps ensure questions are directed at the user, not about them in third person.
    
    Args:
        prop_text: Original proposition text (may contain names)
        
    Returns:
        Normalized text with names converted to "you"/"your"
    """
    # Common patterns to replace
    # "Arnav Sharma" -> "you"
    # "Arnav's" -> "your"
    # "Arnav is" -> "you are"
    # "Arnav has" -> "you have"
    # "Arnav was" -> "you were"
    # "Arnav" -> "you" (standalone)
    
    normalized = prop_text
    
    # Replace common name patterns
    import re
    
    # "Arnav Sharma" or just "Arnav" (but not if followed by apostrophe - handle separately)
    normalized = re.sub(r'\bArnav Sharma\b', 'you', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\bArnav\'s\b', "your", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\bArnav is\b', 'you are', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\bArnav has\b', 'you have', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\bArnav was\b', 'you were', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\bArnav\b', 'you', normalized, flags=re.IGNORECASE)
    
    # Fix any awkward "you you" cases from multiple replacements
    normalized = re.sub(r'\byou you\b', 'you', normalized, flags=re.IGNORECASE)
    
    return normalized


def format_observation_summary(observations: List[Any], max_obs: int = 5) -> str:
    """
    Format observations for prompt inclusion.
    
    Args:
        observations: List of Observation objects
        max_obs: Maximum number of observations to include
        
    Returns:
        Formatted observation summary string
    """
    if not observations:
        return "No specific observations provided."
    
    summaries = []
    for i, obs in enumerate(observations[:max_obs], 1):
        # Handle both dict and object formats
        if isinstance(obs, dict):
            obs_id = obs.get('id', 'unknown')
            obs_text = obs.get('observation_text', obs.get('text', ''))
        else:
            obs_id = getattr(obs, 'id', 'unknown')
            obs_text = getattr(obs, 'observation_text', '')
        
        # Truncate long observations
        if len(obs_text) > 150:
            obs_text = obs_text[:150] + "..."
        
        summaries.append(f"  - obs_{obs_id}: {obs_text}")
    
    if len(observations) > max_obs:
        summaries.append(f"  ... and {len(observations) - max_obs} more observations")
    
    return "\n".join(summaries)

