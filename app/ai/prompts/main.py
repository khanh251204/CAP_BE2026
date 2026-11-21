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


def get_system_prompt(
    current_date: str = None,
    allowed_intents=None,
    allow_multi_item: bool = True,
) -> str:
    if allowed_intents is not None or not allow_multi_item:
        from app.ai.prompts.builder import INTENT_ORDER, build_pruned_system_prompt

        intents = INTENT_ORDER if allowed_intents is None else allowed_intents
        return build_pruned_system_prompt(
            allowed_intents=intents,
            allow_multi_item=allow_multi_item,
            current_date=current_date,
        )
    prompt = SYSTEM_PROMPT
    if current_date:
        prompt += f"\nSystem Date: {current_date}."
    return prompt