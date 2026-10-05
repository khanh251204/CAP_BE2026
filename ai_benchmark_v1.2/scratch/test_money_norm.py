import re

def normalize_money_in_text(text: str) -> str:
    if not text:
        return text

    # Pattern 1: X triệu Y (e.g., 1 triệu 500, 1tr5, 2tr500)
    def repl_x_tr_y(match):
        x = int(match.group(1))
        y_str = match.group(2)
        if len(y_str) == 1:
            y = int(y_str) * 100000
        elif len(y_str) == 2:
            y = int(y_str) * 10000
        elif len(y_str) == 3:
            y = int(y_str) * 1000
        else:
            y = int(y_str)
        val = x * 1000000 + y
        return f"{val} đồng"

    # Pattern for 1 triệu rưỡi, 1tr rưỡi
    text = re.sub(r"(\d+)\s*(?:triệu|tr)\s*rưỡi\b", r"\1 500000 đồng", text, flags=re.IGNORECASE)
    text = re.sub(r"một\s*triệu\s*rưỡi\b", "1500000 đồng", text, flags=re.IGNORECASE)

    # Replace XtrY / X triệu Y
    text = re.sub(r"\b(\d+)\s*(?:triệu|tr)\s*(\d{1,3})\b(?!\s*kg|\s*ký|\s*kí|\s*con|\s*cái|\s*bao|\s*thùng)", repl_x_tr_y, text, flags=re.IGNORECASE)

    # Replace X triệu / Xtr
    def repl_tr(match):
        x = int(match.group(1))
        return f"{x * 1000000} đồng"
    text = re.sub(r"\b(\d+)\s*(?:triệu|tr)\b", repl_tr, text, flags=re.IGNORECASE)

    # Replace Xk / X nghìn / X ngàn
    def repl_k(match):
        x = int(match.group(1))
        return f"{x * 1000} đồng"
    text = re.sub(r"\b(\d+)\s*(?:k|nghìn|ngàn)\b", repl_k, text, flags=re.IGNORECASE)

    # Replace word numbers: 1 triệu, 2 triệu, etc.
    word_money = [
        (r"\bột\s*triệu\b", "1000000 đồng"),
        (r"\bhai\s*triệu\b", "2000000 đồng"),
        (r"\bba\s*triệu\b", "3000000 đồng"),
        (r"\bbốn\s*triệu\b", "4000000 đồng"),
        (r"\bnăm\s*triệu\b", "5000000 đồng"),
        (r"\bmười\s*triệu\b", "10000000 đồng"),
        (r"\bhai\s*mươi\s*triệu\b", "20000000 đồng"),
        (r"\bnăm\s*trăm\s*nghìn\b", "500000 đồng"),
        (r"\bnăm\s*trăm\s*ngàn\b", "500000 đồng"),
        (r"\btám\s*triệu\b", "8000000 đồng"),
    ]
    for p, r in word_money:
        text = re.sub(p, r, text, flags=re.IGNORECASE)

    # Clean up double 'đồng' if present
    text = re.sub(r"đồng\s+đồng", "đồng", text)
    return text


test_cases = [
    "Mua thêm 80 ký tỏi băm hết 2 triệu",
    "Chi 10tr mua heo hơi về mổ bán",
    "Lấy về 5 con heo con giống",
    "Cân bán 20 ký sườn non hết 1tr",
    "Bán cho chị Hương 60 kg mỡ heo giá 80k một kg",
    "Trả 300k tiền đá ướp lạnh",
    "Chi 15tr mua túi nilon đóng gói về mổ bán",
    "1 triệu 500 tiền điện tháng này",
    "5 triệu đồng tiền kho lạnh tháng này",
    "Chốt đơn 2 cây chả lụa giá 2tr một cây",
    "Khách lấy 100 kg giò heo hết 20 triệu đồng",
]

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

for tc in test_cases:
    print(f"BEFORE: {tc}")
    print(f"AFTER : {normalize_money_in_text(tc)}\n")
