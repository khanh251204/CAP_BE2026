# prompts/main.py
from app.ai.prompts.common import COMMON_RULES
from app.ai.prompts.intent import INTENT_RULES
from app.ai.prompts.entity import ENTITY_RULES
from app.ai.prompts.output import OUTPUT_FORMAT_AND_EXAMPLES


MULTI_TURN_RULES = """
# MULTI-TURN RULES
1. Merge: Điền trường null hoặc ghi đè khi sửa đổi. Giữ nguyên giá trị cũ nếu không được nhắc tới.
2. Giữ nguyên `intent` và `type` trừ khi người dùng đổi rõ hành động (ví dụ: "nhầm, bán chứ không mua").
"""

SYSTEM_PROMPT = f"""You are an AI for Vietnamese transaction logging. Parse Speech-to-Text inputs into JSON.
{COMMON_RULES}
{INTENT_RULES}
{ENTITY_RULES}
{MULTI_TURN_RULES}
{OUTPUT_FORMAT_AND_EXAMPLES}
""".strip()


def get_system_prompt(current_date: str = None) -> str:
    prompt = SYSTEM_PROMPT
    if current_date:
        prompt += f"\nSystem Date: {current_date}."
    return prompt