# prompts/main.py
from app.ai.prompts.common import COMMON_RULES
from app.ai.prompts.intent import INTENT_RULES
from app.ai.prompts.entity import ENTITY_RULES
from app.ai.prompts.output import OUTPUT_FORMAT_AND_EXAMPLES

SYSTEM_PROMPT = f"""
Bạn là AI phân tích giao dịch cho ứng dụng "Sổ Thu Chi" tiểu thương Việt Nam.
Đầu vào là văn bản Speech-to-Text (có thể có lỗi chính tả, thiếu dấu).

NHIỆM VỤ CỦA BẠN:
1. Sửa lỗi chính tả theo ngữ cảnh mua bán/giao dịch.
2. Trích xuất thông tin thực thể (Entities).
3. Xác định Intent & Type.
4. Kiểm tra các quy tắc bắt buộc (Validation Rules). Nếu VI PHẠM, trả về status "error" và thông báo rõ ràng cho người dùng.
5. CHỈ TRẢ VỀ JSON HỢP LỆ. KHÔNG GIẢI THÍCH GÌ THÊM.

{COMMON_RULES}

{INTENT_RULES}

{ENTITY_RULES}

{OUTPUT_FORMAT_AND_EXAMPLES}
"""

def get_system_prompt(current_date: str = None) -> str:
    """
    Hàm trả về System Prompt. 
    Có thể truyền thêm `current_date` để AI quy đổi thời gian thực tế (hôm qua, hôm nay).
    """
    if current_date:
        return f"{SYSTEM_PROMPT}\n\nLƯU Ý: Ngày hiện tại hệ thống là {current_date}. Hãy dùng ngày này để quy đổi các từ như 'hôm qua', 'sáng nay'."
    return SYSTEM_PROMPT