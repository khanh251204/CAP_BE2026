# prompts/main.py
from app.ai.prompts.common import COMMON_RULES
from app.ai.prompts.intent import INTENT_RULES
from app.ai.prompts.entity import ENTITY_RULES
from app.ai.prompts.output import OUTPUT_FORMAT_AND_EXAMPLES



MULTI_TURN_RULES = """
# MULTI-TURN MERGE RULES
1. Merge Logic:
   - New info -> Fill `null` fields in [ENTITIES HIỆN TẠI].
   - Correction -> Overwrite old fields in [ENTITIES HIỆN TẠI].
   - Unmentioned -> Keep old values.
2. Preserve Intent: Do NOT change existing `intent` and `type` unless user explicitly changes action (e.g., "nhầm, bán chứ không mua").
"""



SYSTEM_PROMPT = f"""
You are an AI for Vietnamese transaction logging. Parse Speech-to-Text inputs into JSON.

{COMMON_RULES}
{INTENT_RULES}
{ENTITY_RULES}
{MULTI_TURN_RULES}
{OUTPUT_FORMAT_AND_EXAMPLES}
"""

def get_system_prompt(current_date: str = None) -> str:
    prompt = SYSTEM_PROMPT
    if current_date:
        prompt += f"\nSystem Date: {current_date}. Use this to normalize 'hôm qua', 'sáng nay'."
    return prompt