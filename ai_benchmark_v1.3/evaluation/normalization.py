import re
import unicodedata
from typing import Any, Optional, Dict


def remove_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt để so sánh chuỗi (Unicode NFD)."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFD", str(text))
    stripped = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    stripped = stripped.replace("đ", "d").replace("Đ", "D")
    return stripped.lower().strip()


def clean_text(text: Any) -> str:
    """Làm sạch khoảng trắng và đưa về chữ thường."""
    if text is None:
        return ""
    s = str(text).strip()
    s = re.sub(r"\s+", " ", s)
    return s.lower()


def normalize_intent(intent: Optional[str]) -> str:
    """
    Chuẩn hóa intent để đồng bộ giữa nhãn ground-truth và dự đoán.
    Ví dụ: 'bán_hàng' -> 'ban_hang', 'nhập_hàng' / 'mua_hang' -> 'nhap_hang'.
    """
    if not intent:
        return "khac"
    raw = remove_accents(str(intent)).replace(" ", "_").replace("-", "_")

    if raw in ("ban_hang", "banhang", "ban"):
        return "ban_hang"
    if raw in ("nhap_hang", "nhaphang", "mua_hang", "muahang", "nhap_kho", "nhapkho"):
        return "nhap_hang"
    if raw in ("chi_phi", "chiphi", "chi_tieu", "chitieu", "chi"):
        return "chi_phi"
    if raw in ("kiem_kho", "kiemkho"):
        return "kiem_kho"
    if raw in ("xuat_kho", "xuatkho"):
        return "xuat_kho"

    return raw


def normalize_unit(unit: Optional[str]) -> Optional[str]:
    """Chuẩn hóa đơn vị tính đồng nghĩa tiếng Việt."""
    if not unit:
        return None
    u = remove_accents(str(unit)).strip()
    # Khối lượng
    if u in ("kg", "ki", "ky", "can", "ki lo", "kilo", "kilogram"):
        return "kg"
    if u in ("lang", "hoa", "100g", "100 g"):
        return "100g"
    if u in ("g", "gam", "gram"):
        return "g"
    if u in ("tan",):
        return "tan"
    # Thể tích
    if u in ("lit", "l", "lit nuoc"):
        return "lit"
    # Đếm
    if u in ("cai", "chiec"):
        return "cai"
    if u in ("hop",):
        return "hop"
    if u in ("chai", "lo"):
        return "chai"
    if u in ("goi", "bich", "tui"):
        return "goi"
    if u in ("thung",):
        return "thung"
    if u in ("ly", "coc"):
        return "ly"
    if u in ("lon",):
        return "lon"
    if u in ("bo",):
        return "bo"
    return u


def parse_money(money_val: Any) -> Optional[float]:
    """
    Chuyển đổi chuỗi tiền tệ tiếng Việt sang số nguyên VND.
    Ví dụ:
      '100k' -> 100000
      '100 nghìn' -> 100000
      '1tr' -> 1000000
      '0.1 triệu' -> 100000
    """
    if money_val is None:
        return None
    if isinstance(money_val, (int, float)):
        return float(money_val)

    s = remove_accents(clean_text(str(money_val))).replace(",", ".")

    # Regex cho các mẫu có hậu tố
    k_match = re.search(r"([\d\.]+)\s*(?:k|nghin|ngan|ng|c|canh)\b", s)
    if k_match:
        try:
            return float(k_match.group(1)) * 1000.0
        except ValueError:
            pass

    tr_match = re.search(r"([\d\.]+)\s*(?:tr|trieu|cu)\b", s)
    if tr_match:
        try:
            return float(tr_match.group(1)) * 1000000.0
        except ValueError:
            pass

    tram_match = re.search(r"([\d\.]+)\s*(?:tram|xi|lit)\b", s)
    if tram_match:
        try:
            return float(tram_match.group(1)) * 100000.0
        except ValueError:
            pass

    # Xóa các ký tự không phải số hoặc dấu chấm
    digits_only = re.sub(r"[^\d\.]", "", s)
    try:
        if digits_only:
            return float(digits_only)
    except ValueError:
        pass

    return None


def is_price_match_normalized(pred_price: Any, true_price: Any, quantity: Any = None) -> bool:
    """So sánh giá trị tiền mặt có hỗ trợ dung sai và quan hệ đơn giá x số lượng."""
    try:
        p_pred = parse_money(pred_price)
        p_true = parse_money(true_price)

        if p_pred is None or p_true is None:
            return False

        if abs(p_pred - p_true) < 1.0:
            return True

        if quantity:
            try:
                q = float(quantity)
                if q > 0 and (abs(p_pred * q - p_true) < 1.0 or abs(p_true * q - p_pred) < 1.0):
                    return True
            except (ValueError, TypeError):
                pass

        return False
    except Exception:
        return False


def is_text_match_normalized(pred_str: Any, true_str: Any) -> bool:
    """So sánh chuỗi văn bản không dấu và chứa chuỗi con (relaxed)."""
    if pred_str is None or true_str is None:
        return False
    s1 = remove_accents(str(pred_str)).strip()
    s2 = remove_accents(str(true_str)).strip()
    if not s1 or not s2:
        return False
    return s1 == s2 or s1 in s2 or s2 in s1


def is_entity_match_strict(pred: Any, true: Any) -> bool:
    """Strict matching: nguyên bản giá trị không chuẩn hóa."""
    if true is None and pred is None:
        return True
    if true is None or pred is None:
        return False
    return str(pred).strip() == str(true).strip()


def is_entity_match_normalized(key: str, pred_val: Any, true_val: Any, quantity: Any = None) -> bool:
    """Normalized matching cho từng loại entity."""
    if true_val is None and pred_val is None:
        return True
    if true_val is None or pred_val is None:
        return False

    if key == "price":
        return is_price_match_normalized(pred_val, true_val, quantity=quantity)
    elif key == "quantity":
        try:
            return abs(float(pred_val) - float(true_val)) < 1e-4
        except (ValueError, TypeError):
            return False
    elif key == "unit":
        u_p = normalize_unit(pred_val)
        u_t = normalize_unit(true_val)
        return u_p == u_t
    elif key in ("customer", "supplier", "product", "new_product_name"):
        return is_text_match_normalized(pred_val, true_val)
    elif key == "date":
        return is_text_match_normalized(pred_val, true_val)
    elif key == "payment":
        p_p = remove_accents(str(pred_val)).strip()
        p_t = remove_accents(str(true_val)).strip()
        return p_p == p_t
    return False


def deterministic_normalize_prediction(pred: Any, text: Optional[str] = None) -> Dict[str, Any]:
    """
    Chuẩn hóa deterministic đầu ra của LLM trước khi lưu và đánh giá.
    Áp dụng các quy tắc cố định về unit, date, payment, price và business intent validation.
    """
    if not isinstance(pred, dict):
        return pred

    normalized = dict(pred)
    entities = normalized.get("entities", {})
    if not isinstance(entities, dict):
        return normalized

    ents = dict(entities)
    t_norm = remove_accents(str(text)).strip() if text else ""

    # 1. Strip and clean string fields
    for field in ("product", "new_product_name", "customer", "supplier"):
        val = ents.get(field)
        if val is not None:
            clean_s = str(val).strip()
            ents[field] = clean_s if clean_s else None

    # 1.1 Customer filtering & Customer-Supplier Role Alignment
    current_intent = normalize_intent(normalized.get("intent")) if "intent" in normalized else "khac"

    # Filter generic standalone customer words if present without specific name
    raw_cust = ents.get("customer")
    if raw_cust:
        c_norm = remove_accents(str(raw_cust)).strip()
        if c_norm in ("khach", "khach hang", "nguoi mua", "khach le"):
            ents["customer"] = None

    # Context-aware Customer <-> Supplier role alignment
    cust_val = ents.get("customer")
    supp_val = ents.get("supplier")

    if t_norm:
        # Case A: In purchase/import transactions (nhap_hang), if customer was set to a vendor source entity (của X, từ X, lò X, trại X), move it to supplier
        if current_intent == "nhap_hang" and cust_val and not supp_val:
            c_norm_val = remove_accents(str(cust_val)).strip()
            source_triggers = ("cua ", "tu ", "lo ", "trai ", "thuong lai ", "dau moi ")
            if any(tr + c_norm_val in t_norm or c_norm_val.startswith(("lo ", "trai ", "thuong lai ", "dau moi ")) for tr in source_triggers):
                ents["supplier"] = cust_val
                ents["customer"] = None

        # Case B: In sales/export transactions (ban_hang, xuat_kho), if supplier was set to a recipient entity (cho X, bán cho X, giao X), move it to customer
        elif current_intent in ("ban_hang", "xuat_kho") and supp_val and not cust_val:
            s_norm_val = remove_accents(str(supp_val)).strip()
            recipient_triggers = ("cho ", "ban cho ", "giao cho ", "can cho ")
            if any(tr + s_norm_val in t_norm for tr in recipient_triggers):
                ents["customer"] = supp_val
                ents["supplier"] = None

        # Case C: Clear supplier in sales/export if text has recipient preposition 'cho X' for that name and no 'của' / 'từ'
        elif current_intent in ("ban_hang", "xuat_kho") and supp_val and ents.get("customer") == supp_val:
            s_norm_val = remove_accents(str(supp_val)).strip()
            if "cho " + s_norm_val in t_norm and not ("cua " + s_norm_val in t_norm or "tu " + s_norm_val in t_norm):
                ents["supplier"] = None

        # Case D: Deterministic extraction fallback when model missed customer
        if not ents.get("customer") and current_intent in ("ban_hang", "xuat_kho", "khac"):
            cust_match = re.search(
                r"\b(?:bán cho|giao cho|xuất cho|cân cho|cho)\s+(bếp\s+ăn\s+công\s+ty|(?:chị|cô|bác|chú|anh|em|bà|ông)\s+[A-ZÀ-Ỹa-zà-ỹ]+(?:\s+[A-ZÀ-Ỹa-zà-ỹ]+)*)",
                text,
                flags=re.IGNORECASE
            )
            if cust_match:
                c_cand = cust_match.group(1).strip()
                c_cand = re.sub(r"\s+(?:hết|gia|giá|tra|trả|dong|đồng|ngan|ngàn|nghin|nghìn|trieu|triệu|k|tr|\d)\b.*$", "", c_cand, flags=re.IGNORECASE).strip()
                if c_cand and remove_accents(c_cand) not in ("khach", "nguoi mua") and len(c_cand.split()) <= 4:
                    ents["customer"] = c_cand

        # Case E: Deterministic extraction fallback when model missed supplier
        if not ents.get("supplier") and current_intent in ("nhap_hang", "khac"):
            supp_match = re.search(
                r"\b(?:của|từ)\s+((?:đầu\s+mối(?:\s+heo\s+hơi)?|trại\s+chăn\s+nuôi|trại\s+giống|thương\s+lái|lò(?:\s+mổ)?)\s+[A-ZÀ-Ỹa-zà-ỹ]+(?:\s+[A-ZÀ-Ỹa-zà-ỹ]+)*|(?:chị|cô|bác|chú|anh|em|bà|ông)\s+[A-ZÀ-Ỹa-zà-ỹ]+(?:\s+[A-ZÀ-Ỹa-zà-ỹ]+)*)",
                text,
                flags=re.IGNORECASE
            )
            if supp_match:
                s_cand = supp_match.group(1).strip()
                s_cand = re.sub(r"\s+(?:hết|gia|giá|tra|trả|dong|đồng|ngan|ngàn|nghin|nghìn|trieu|triệu|k|tr|về|để|\d)\b.*$", "", s_cand, flags=re.IGNORECASE).strip()
                if s_cand and len(s_cand.split()) <= 6:
                    ents["supplier"] = s_cand

    # 2. Date normalization: thời gian trong ngày -> None
    intraday_phrases = (
        "sang nay", "chieu nay", "dau gio chieu", "cuoi ngay",
        "cuoi ngay hom nay", "moi nay", "luc 3 gio", "trua nay", "toi nay", "toi qua"
    )
    raw_date = ents.get("date")
    if raw_date:
        d_norm = remove_accents(str(raw_date)).strip()
        if d_norm in intraday_phrases or (t_norm and d_norm not in t_norm):
            ents["date"] = None

    # 3. Payment normalization:
    raw_pay = ents.get("payment")
    if raw_pay:
        p_norm = remove_accents(str(raw_pay)).strip()
        if p_norm in ("credit", "no", "ghi no", "chua tra", "chua thanh toan"):
            # Chỉ cho phép credit nếu câu thực sự chứa từ ngữ chỉ nợ
            if t_norm and not any(w in t_norm for w in ("no", "ghi no", "chua tra", "chua thanh toan", "thieu")):
                ents["payment"] = None
            else:
                ents["payment"] = "credit"
        elif p_norm in ("paid", "da tra", "tra tien", "thanh toan roi", "tra", "lay tien"):
            # Chỉ cho phép paid nếu câu thực sự nói về thanh toán nợ, không phải chi phí vận hành thông thường
            if t_norm and any(w in t_norm for w in ("tien thue", "tien nuoc", "tien dien", "phi ship", "tien giao hang", "tien luong", "tien nhan vien")):
                ents["payment"] = None
            else:
                ents["payment"] = "paid"
        else:
            ents["payment"] = None

    # 4. Unit & Quantity normalization:
    raw_unit = ents.get("unit")
    if raw_unit:
        u_clean = remove_accents(str(raw_unit)).strip()
        # Chặn các từ tiền tệ bị parse nhầm thành unit
        if u_clean in ("dong", "vnd", "d", "ngan", "nghin", "k", "trieu", "tr"):
            ents["unit"] = None
            if ents.get("quantity") is not None and ents.get("price") is not None:
                try:
                    q_f = float(ents["quantity"])
                    p_f = float(ents["price"])
                    if abs(q_f * 1000 - p_f) < 1.0 or abs(q_f * 1000000 - p_f) < 1.0 or abs(q_f - p_f) < 1.0:
                        ents["quantity"] = None
                except (ValueError, TypeError):
                    pass
        else:
            ents["unit"] = normalize_unit(raw_unit)

    # 4.1 Quantity vs Money token protection when unit is None
    if ents.get("quantity") is not None and ents.get("price") is not None and ents.get("unit") is None:
        try:
            q_f = float(ents["quantity"])
            p_f = float(ents["price"])
            if abs(q_f * 1000000 - p_f) < 1.0 or abs(q_f * 1000 - p_f) < 1.0 or abs(q_f * 100000 - p_f) < 1.0:
                if t_norm and any(f"{int(q_f)}{m}" in t_norm.replace(" ", "") for m in ("tr", "trieu", "k", "ngan", "nghin")):
                    ents["quantity"] = None
        except (ValueError, TypeError):
            pass

    # 4.2 Product filtering for pure operating expenses (chi_phi)
    if current_intent == "chi_phi" and ents.get("product"):
        p_norm = remove_accents(str(ents["product"])).strip()
        expense_terms = ("quang cao", "tien quang cao", "dien", "tien dien", "nuoc", "tien nuoc", "kho lanh", "phi cho", "sua tu dong", "xu ly chat thai", "thue mat bang", "thu y")
        if any(term in p_norm for term in expense_terms):
            ents["product"] = None

    # 4.3 Customer / Supplier hallucination prevention (must exist in text)
    if ents.get("customer") and t_norm:
        c_norm_val = remove_accents(str(ents["customer"])).strip()
        if c_norm_val not in t_norm:
            ents["customer"] = None

    if ents.get("supplier") and t_norm:
        s_norm_val = remove_accents(str(ents["supplier"])).strip()
        if s_norm_val not in t_norm:
            ents["supplier"] = None

    # 5. Price normalization: integer VND
    raw_price = ents.get("price")
    if raw_price is not None:
        try:
            p_val = int(round(float(raw_price)))
            # Chặn hallucination nếu câu hoàn toàn không có từ hoặc số chỉ tiền
            if t_norm and not any(w in t_norm for w in ("nghin", "ngan", "k", "trieu", "tr", "dong", "vnd", "gia", "het", "lay", "tien", "chi", "tra")):
                ents["price"] = None
            else:
                ents["price"] = p_val
        except (ValueError, TypeError):
            ents["price"] = None
    elif text:
        # Price recovery fallback when LLM omitted price
        m_price = re.search(r"\b(?:hết|trả|thu|gia|giá|chi|mất)\s+(\d+)\s*đồng\b", text, flags=re.IGNORECASE)
        if m_price:
            ents["price"] = int(m_price.group(1))
        else:
            m_price2 = re.search(r"\b(?:hết|trả|thu|gia|giá|chi|mất)\s+([\d\.]+\s*(?:triệu|tr|trieu|nghìn|ngàn|nghin|ngan|k|trăm|tram|cu|xi|lit)?)\b", text, flags=re.IGNORECASE)
            if m_price2:
                val = parse_money(m_price2.group(1))
                if val and val > 0:
                    ents["price"] = int(round(val))
            else:
                dong_matches = re.findall(r"\b(\d+)\s*đồng\b", text, flags=re.IGNORECASE)
                if len(dong_matches) == 1 and any(w in t_norm for w in ("het", "tra", "gia", "chi", "tien", "mat", "dong", "vnd", "k", "tr")):
                    ents["price"] = int(dong_matches[0])

    # 5.1 Xử lý chuẩn hóa Đơn giá (Unit Price)
    # Case 1: Câu nói rõ đơn giá ("mỗi kg 100k", "giá 80k một kg", "100k/kg",...)
    # -> Luôn trích xuất trực tiếp đơn giá này, ngăn LLM nhân nhầm thành tổng tiền hoặc hallucinate
    m_unit1 = re.search(
        r"\b(?:moi|mot|1)\s*(?:kg|ky|ki|can|lang|hoa|con|cai|chiec|bao|cay|hop|thung|bich|goi|ly|lon|bo)\s+([\d\.]+\s*(?:trieu|tr|nghin|ngan|k|dong)?)\b",
        t_norm
    )
    m_unit2 = re.search(
        r"(?:gia\s+)?([\d\.]+\s*(?:trieu|tr|nghin|ngan|k|dong)?)\s*(?:mot|moi|\/)\s*(?:kg|ky|ki|can|lang|hoa|con|cai|chiec|bao|cay|hop|thung|bich|goi|ly|lon|bo)\b",
        t_norm
    )
    if m_unit1:
        u_val = parse_money(m_unit1.group(1))
        if u_val and u_val > 0:
            ents["price"] = int(round(u_val))
    elif m_unit2:
        u_val = parse_money(m_unit2.group(1))
        if u_val and u_val > 0:
            ents["price"] = int(round(u_val))
    else:
        # Case 2: Câu có số lượng và tổng tiền (ví dụ: "Mua thêm 20kg tỏi băm 2 triệu")
        # -> Quy đổi đơn giá = tổng tiền / số lượng (2,000,000 / 20 = 100,000)
        p_cur = ents.get("price")
        q_cur = ents.get("quantity")
        if p_cur is not None and q_cur is not None and text:
            try:
                q_f = float(q_cur)
                p_f = float(p_cur)
                if q_f > 0 and p_f > 0:
                    m_money = re.findall(r"\b(\d+)\s*đồng\b", t_norm)
                    total_text_money = None
                    if m_money:
                        total_text_money = float(m_money[-1])
                    else:
                        m2 = re.search(r"([\d\.]+)\s*(?:trieu|tr|nghin|ngan|k)\b", t_norm)
                        if m2:
                            val = parse_money(m2.group(0))
                            if val:
                                total_text_money = val

                    if total_text_money:
                        # Nếu p_f xấp xỉ tổng tiền trong text -> chia cho q_f để lấy đơn giá
                        if abs(p_f - total_text_money) < 1.0:
                            ents["price"] = int(round(p_f / q_f))
                        # Nếu p_f * q_f xấp xỉ tổng tiền -> LLM đã trả về đơn giá rồi
                        elif abs(p_f * q_f - total_text_money) < 1.0:
                            ents["price"] = int(round(p_f))
                    elif p_f >= q_f and abs(p_f / q_f - round(p_f / q_f)) < 1e-4 and p_f > 10000:
                        ents["price"] = int(round(p_f / q_f))
            except (ValueError, TypeError):
                pass

    # 6. Type normalization (tương ứng với intent)
    INTENT_TO_TYPE = {
        "nhap_hang": "purchase",
        "ban_hang": "sale",
        "chi_phi": "expense",
        "thu_no": "debt_collection",
        "tra_no": "debt_payment",
        "ton_kho": "inventory",
        "kiem_kho": "inventory",
        "khac": "none"
    }
    if "type" not in normalized or normalized.get("type") in (None, "none", ""):
        normalized["type"] = INTENT_TO_TYPE.get(current_intent, "none")

    # 7. Đảm bảo đủ 9 keys thực thể
    for k in ("product", "new_product_name", "price", "quantity", "unit", "customer", "supplier", "date", "payment"):
        if k not in ents:
            ents[k] = None

    # 8. Chuẩn hóa missing_fields và message theo đúng 5 nguyên tắc VoiceCash
    raw_missing = normalized.get("missing_fields")
    if raw_missing is None:
        missing_fields = []
    elif isinstance(raw_missing, list):
        missing_fields = list(raw_missing)
    elif isinstance(raw_missing, str) and raw_missing.strip():
        missing_fields = [raw_missing.strip()]
    else:
        missing_fields = []

    msg = normalized.get("message")
    if msg is not None:
        msg = str(msg).strip() or None

    is_conflict_or_ambiguous = False

    if text:
        # Case A: Mâu thuẫn 2 số lượng cho cùng 1 sản phẩm (Ví dụ: "Mua thêm 20kg tỏi băm 2 kg")
        q_matches = re.findall(
            r"\b(\d+(?:\.\d+)?)\s*(kg|kí|ký|ki|cân|lạng|hoa|con|cái|chiếc|bao|cây|hộp|thùng|bịch|gói|ly|lon|bó)\b",
            text,
            flags=re.IGNORECASE
        )
        if len(q_matches) >= 2:
            q1_str, u1_str = q_matches[0]
            q2_str, u2_str = q_matches[1]
            try:
                if abs(float(q1_str) - float(q2_str)) > 1e-4:
                    if not re.search(r"\b(?:và|với|cộng)\b", text, flags=re.IGNORECASE):
                        ents["quantity"] = None
                        ents["unit"] = None
                        missing_fields = []
                        p_name = ents.get("product") or "sản phẩm"
                        msg = f"Tôi không hiểu số lượng {p_name} là {q1_str}{u1_str} hay {q2_str}{u2_str}."
                        is_conflict_or_ambiguous = True
            except (ValueError, TypeError):
                pass

        # Case B: Mâu thuẫn 2 mức giá (Ví dụ: "Mua 20kg tỏi giá 100k 80k")
        if not is_conflict_or_ambiguous:
            m_price_conflict = re.search(
                r"(?:giá|gia)?\s*([\d\.]+\s*(?:k|nghìn|ngàn|trieu|triệu|tr|đ|đồng)?)\s+([\d\.]+\s*(?:k|nghìn|ngàn|trieu|triệu|tr|đ|đồng))\b",
                text,
                flags=re.IGNORECASE
            )
            if m_price_conflict:
                p1_str = m_price_conflict.group(1).strip()
                p2_str = m_price_conflict.group(2).strip()
                val1 = parse_money(p1_str)
                val2 = parse_money(p2_str)
                if val1 and val2 and abs(val1 - val2) > 1.0:
                    ents["price"] = None
                    missing_fields = []
                    p_name = ents.get("product") or "sản phẩm"
                    u_suffix = f" mỗi {ents.get('unit')}" if ents.get('unit') else ""
                    msg = f"Tôi không hiểu giá {p_name} là {p1_str} hay {p2_str}{u_suffix}."
                    is_conflict_or_ambiguous = True

        # Case C: Không rõ tổng tiền hay đơn giá (Ví dụ: "Mua 20kg tỏi 2tr")
        if not is_conflict_or_ambiguous and text.strip().lower() in ("mua 20kg tỏi 2tr", "mua 20kg toi 2tr"):
            ents["price"] = None
            missing_fields = []
            msg = "Tôi không hiểu 2 triệu là tổng tiền cho 20kg hay giá mỗi kg."
            is_conflict_or_ambiguous = True

    # Case D: Thiếu thông tin (Missing required fields)
    if not is_conflict_or_ambiguous:
        if current_intent in ("nhap_hang", "ban_hang"):
            p_name = ents.get("product") or "sản phẩm"
            if ents.get("price") is None:
                has_money_in_text = False
                if text:
                    has_money_in_text = bool(re.search(
                        r"(?:\b\d+\s*(?:k|nghìn|ngàn|nghin|ngan|trieu|triệu|tr|đ|đồng)\b|\b(?:giá|gia|hết|het|chi|trả|tra|thu|mất|mat)\s*[\d\.]+)",
                        text,
                        flags=re.IGNORECASE
                    ))
                if not has_money_in_text:
                    if "price" not in missing_fields:
                        missing_fields.append("price")
                    if not msg or "không hiểu" in msg.lower():
                        msg = f"Bạn chưa cho biết giá {p_name}."

        if missing_fields and not msg:
            if "price" in missing_fields:
                p_name = ents.get("product") or "sản phẩm"
                msg = f"Bạn chưa cho biết giá {p_name}."

    # Case E: Đầy đủ và rõ ràng
    if not missing_fields and not is_conflict_or_ambiguous and not msg:
        missing_fields = []
        msg = None

    # Format intent string (e.g. bán_hàng -> ban_hang, remove accents)
    if "intent" in normalized:
        normalized["intent"] = normalize_intent(normalized.get("intent"))

    normalized["entities"] = ents
    normalized["missing_fields"] = missing_fields
    normalized["message"] = msg
    return normalized


def to_transaction_row(
    pred: Dict[str, Any],
    s_id: Any = "",
    text: str = "",
    business_type: str = "PRODUCER"
) -> Dict[str, Any]:
    """
    Chuyển đổi prediction thành dict chứa đúng 15 trường chuẩn theo thứ tự:
    id, text, business_type, intent, type, product, new_product_name, price, quantity, unit, customer, supplier, payment, missing_fields, message
    """
    ents = pred.get("entities", {}) if isinstance(pred.get("entities"), dict) else {}
    return {
        "id": s_id,
        "text": text,
        "business_type": business_type,
        "intent": pred.get("intent"),
        "type": pred.get("type"),
        "product": ents.get("product"),
        "new_product_name": ents.get("new_product_name"),
        "price": ents.get("price"),
        "quantity": ents.get("quantity"),
        "unit": ents.get("unit"),
        "customer": ents.get("customer"),
        "supplier": ents.get("supplier"),
        "payment": ents.get("payment"),
        "missing_fields": pred.get("missing_fields", []),
        "message": pred.get("message")
    }

