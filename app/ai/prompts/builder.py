"""
Dynamic System Prompt Builder (Prompt Pruning theo gói / tập intent được cấp cho user).

Mục tiêu:
- Khi tài khoản chỉ được cấp 2 intent (vd gói 50k: ban_hang, mua_hang), chỉ đưa vào prompt
  đúng bảng intent, quy tắc phân biệt, quy tắc entity và JSON schema cần thiết.
- Giảm mạnh số token đầu vào (~50-65% cho gói 2 intent) -> giảm chi phí LLM, giảm TTFT/latency,
  đồng thời tăng độ chính xác phân loại vì giảm nhiễu từ các intent không được dùng.
- Dùng `lru_cache` theo tập intent chuẩn hóa -> chi phí dựng prompt ~0.01ms.
"""
from functools import lru_cache
from typing import Dict, FrozenSet, Iterable, List, Optional, Tuple

from app.ai.prompts.common import COMMON_RULES

# Thứ tự chuẩn 17 intent trong bảng prompt
INTENT_ORDER: Tuple[str, ...] = (
    "ban_hang",
    "mua_hang",
    "nhap_kho",
    "xuat_kho",
    "kiem_kho",
    "khach_ghi_no",
    "thu_no_khach",
    "ghi_no_nha_cung_cap",
    "tra_no_nha_cung_cap",
    "chi_phi",
    "hang_hong",
    "them_san_pham",
    "sua_san_pham",
    "xoa_san_pham",
    "tim_san_pham",
    "bao_cao",
    "chot_so",
)

INTENT_TABLE_ROWS: Dict[str, str] = {
    "ban_hang": "| ban_hang | product, quantity | Bán hàng cho khách (giá không bắt buộc) |",
    "mua_hang": "| mua_hang / nhap_hang | product, quantity | Mua/nhập hàng từ nhà cung cấp (cùng một nghiệp vụ; trích xuất giá nhập & đơn vị nếu có) |",
    "nhap_kho": "| nhap_kho | product, quantity | Nhập kho KHÔNG mất tiền: tồn đầu kỳ, hàng được tặng, khách trả lại, sản xuất xong nhập kho |",
    "xuat_kho": "| xuat_kho | product, quantity | Xuất kho đơn thuần |",
    "kiem_kho": "| kiem_kho | product | Hỏi tồn kho, hoặc kiểm kê: báo số lượng đếm thực tế (quantity = số đếm) |",
    "khach_ghi_no": "| ghi_no_khach_hang / khach_ghi_no | customer | Ghi nợ cho khách (bắt buộc customer; price không bắt buộc nếu có product) |",
    "thu_no_khach": "| thu_no_khach_hang / thu_no_khach | customer, price | Khách trả nợ (bắt buộc customer, price) |",
    "ghi_no_nha_cung_cap": "| ghi_no_nha_cung_cap | supplier, price | Nợ tiền nhà cung cấp |",
    "tra_no_nha_cung_cap": "| tra_no_nha_cung_cap | supplier, price | Trả nợ nhà cung cấp |",
    "chi_phi": "| chi_phi | price | Chi phí kinh doanh (tiền điện, mặt bằng, vận chuyển...) |",
    "hang_hong": "| hang_hong | product, quantity, unit | Báo hàng hư hỏng/hết hạn |",
    "them_san_pham": "| them_san_pham | product | Thêm sản phẩm mới |",
    "sua_san_pham": "| sua_san_pham | product | Sửa sản phẩm |",
    "xoa_san_pham": "| xoa_san_pham | product | Xóa sản phẩm |",
    "tim_san_pham": "| tim_san_pham / xem_san_pham | product | Tìm kiếm/tra cứu sản phẩm |",
    "bao_cao": "| bao_cao | (none) | Báo cáo doanh thu, sổ sách |",
    "chot_so": "| chot_so | (none) | Chốt sổ cuối ngày / tháng / quý / năm |",
}

# Quy tắc phân biệt theo từng nhóm intent:
# (mode, required_intents, text)
# - mode == "all": chỉ đưa vào khi TẤT CẢ intents trong required_intents đều bật
# - mode == "any": đưa vào khi CÓ ÍT NHẤT 1 intent trong required_intents bật
DISAMBIGUATION_RULES: Tuple[Tuple[str, FrozenSet[str], str], ...] = (
    (
        "all",
        frozenset({"mua_hang", "nhap_kho"}),
        '   - `mua_hang` vs `nhap_kho`: nhập hàng mặc định là MUA (mất tiền) -> `mua_hang`, kể cả khi có chữ "nhập kho", '
        '"thêm/nhập ... vào kho", có hay không có giá. Chỉ dùng `nhap_kho` khi câu nói rõ là KHÔNG mất tiền '
        '("tồn đầu", "hàng tặng", "khách trả lại", "sản xuất xong nhập kho").',
    ),
    (
        "all",
        frozenset({"ban_hang", "xuat_kho"}),
        '   - `ban_hang` vs `xuat_kho`: có từ "xuất kho" hoặc xuất nội bộ -> `xuat_kho`; '
        '"xuất"/"giao" hàng cho khách hoặc có giá bán, KHÔNG có chữ "kho" -> `ban_hang`.',
    ),
    (
        "all",
        frozenset({"ban_hang", "khach_ghi_no"}),
        '   - `ban_hang` vs `khach_ghi_no` (BÁN NỢ): Có hàng hóa cụ thể (product + quantity) kèm "nợ", "chịu", "ghi sổ", '
        '"trả sau", "thiếu lại" -> `ban_hang` với payment="PENDING". '
        'Chỉ ghi nợ một số tiền, không kèm số lượng hàng -> `khach_ghi_no`.',
    ),
    (
        "all",
        frozenset({"chi_phi", "tra_no_nha_cung_cap"}),
        '   - `chi_phi` vs `tra_no_nha_cung_cap`: "thanh toán", "đóng", "trả", "chi" + khoản chi vận hành '
        '(điện, nước, mặt bằng, lương, vận chuyển, bốc xếp...) mà KHÔNG có "nợ" và KHÔNG nêu NCC -> `chi_phi`. '
        'Chỉ khi trả nợ cho NHÀ CUNG CẤP -> `tra_no_nha_cung_cap`.',
    ),
    (
        "all",
        frozenset({"chi_phi", "mua_hang"}),
        '   - `chi_phi` vs `mua_hang`: "Chi"/"Bỏ ra" + mua/lấy NGUYÊN LIỆU, hàng hóa để bán/sản xuất -> `mua_hang`.',
    ),
    (
        "all",
        frozenset({"ban_hang", "chot_so"}),
        '   - `ban_hang` vs `chot_so`: "chốt đơn" + hàng hóa -> `ban_hang`; `chot_so` chỉ dùng cho chốt sổ/khóa sổ theo kỳ.',
    ),
    (
        "all",
        frozenset({"mua_hang", "them_san_pham"}),
        '   - `mua_hang` vs `them_san_pham`: "thêm/nhập N <hàng> vào kho" (có số lượng) -> `mua_hang`; '
        '`them_san_pham` chỉ khi tạo MẶT HÀNG MỚI trong danh mục (thường kèm giá, không có số lượng tồn).',
    ),
    (
        "any",
        frozenset({"khach_ghi_no", "thu_no_khach", "ghi_no_nha_cung_cap", "tra_no_nha_cung_cap"}),
        '   - Hướng công nợ (xét ai trả cho ai): '
        'tên người ĐỨNG TRƯỚC "trả"/"gửi lại" hoặc "thu nợ X" -> `thu_no_khach`; '
        'tên ĐỨNG SAU "trả (nợ/bớt) (cho)" hoặc trả đại lý/NCC -> `tra_no_nha_cung_cap`; '
        '"X nợ tôi / còn thiếu / ghi nợ X" -> `khach_ghi_no`; '
        '"Còn nợ / ghi nợ đại lý, công ty, NCC X" -> `ghi_no_nha_cung_cap`.',
    ),
    (
        "any",
        frozenset({"ban_hang"}),
        '   - Dịch vụ làm cho khách (cắt tóc, sửa xe, thay nhớt, giặt ủi, rửa xe, làm móng...) có thu tiền -> '
        '`ban_hang` (product = tên dịch vụ, quantity = null).',
    ),
    (
        "any",
        frozenset({"kiem_kho"}),
        '   - `kiem_kho`: hỏi còn hàng ("coca còn không") -> quantity=null; '
        'báo số đếm thực tế ("kiểm kho coca còn 15 lon") -> quantity = số đếm thực tế.',
    ),
    (
        "all",
        frozenset({"tim_san_pham", "kiem_kho"}),
        '   - `tim_san_pham` vs `kiem_kho`: hỏi CÓ BÁN / giá bán ("có bán X không", "X giá bao nhiêu") -> `tim_san_pham`; '
        'hỏi CÒN bao nhiêu / còn hàng không -> `kiem_kho`.',
    ),
    (
        "any",
        frozenset({"sua_san_pham", "them_san_pham"}),
        '   - `new_product_name` CHỈ dùng khi `sua_san_pham` ĐỔI TÊN ("đổi tên A thành B": product=A, new_product_name=B). '
        'Các trường hợp khác để null.',
    ),
    (
        "all",
        frozenset({"chot_so", "bao_cao"}),
        '   - `chot_so` vs `bao_cao`: có từ "chốt sổ", "khóa sổ", "chốt ca" -> `chot_so`; '
        'chỉ xem số liệu ("doanh thu hôm nay", "báo cáo tháng này") -> `bao_cao`.',
    ),
)

# Nhóm intent theo loại entity sử dụng để lược bỏ phần entity/schema thừa
PRODUCT_INTENTS = frozenset({
    "ban_hang", "mua_hang", "nhap_kho", "xuat_kho", "kiem_kho",
    "hang_hong", "them_san_pham", "sua_san_pham", "xoa_san_pham", "tim_san_pham",
    "khach_ghi_no",
})
QUANTITY_INTENTS = frozenset({
    "ban_hang", "mua_hang", "nhap_kho", "xuat_kho", "kiem_kho", "hang_hong",
})
PRICE_INTENTS = frozenset({
    "ban_hang", "mua_hang", "khach_ghi_no", "thu_no_khach",
    "ghi_no_nha_cung_cap", "tra_no_nha_cung_cap", "chi_phi",
    "them_san_pham", "sua_san_pham",
})
MONEY_ONLY_INTENTS = frozenset({
    "chi_phi", "khach_ghi_no", "thu_no_khach", "ghi_no_nha_cung_cap", "tra_no_nha_cung_cap",
})
CUSTOMER_INTENTS = frozenset({"ban_hang", "khach_ghi_no", "thu_no_khach"})
SUPPLIER_INTENTS = frozenset({"mua_hang", "ghi_no_nha_cung_cap", "tra_no_nha_cung_cap"})
PAYMENT_INTENTS = frozenset({
    "ban_hang", "mua_hang", "khach_ghi_no", "thu_no_khach",
    "ghi_no_nha_cung_cap", "tra_no_nha_cung_cap", "chi_phi",
})
MULTI_ITEM_INTENTS = frozenset({"ban_hang", "mua_hang"})


def _build_intent_section(enabled: FrozenSet[str]) -> str:
    rows = [INTENT_TABLE_ROWS[name] for name in INTENT_ORDER if name in enabled]
    rows.append("| khac | (none) | Không thuộc các nghiệp vụ trên |")
    table = "\n".join([
        "## INTENTS & REQUIRED FIELDS",
        "| Intent | Required Fields | Nghiệp vụ |",
        "|---|---|---|",
        *rows,
    ])

    disamb: List[str] = []
    for mode, req, rule_text in DISAMBIGUATION_RULES:
        if mode == "all" and req.issubset(enabled):
            disamb.append(rule_text)
        elif mode == "any" and (req & enabled):
            disamb.append(rule_text)

    rules_lines = [
        "## INTENT RULES",
        '0. `intent` CHỈ được lấy từ cột Intent trong bảng trên. Tuyệt đối không tự đặt tên intent mới. '
        'Mọi yêu cầu nằm ngoài bảng trên -> trả về "khac".',
        '1. Chọn đúng 1 intent. Đủ required -> status="success". Thiếu required -> status="error", ghi tên field vào missing_fields.',
        "2. Entity không có trong câu -> null. Tuyệt đối không tự suy diễn hay bịa tên người, sản phẩm.",
    ]
    if disamb:
        rules_lines.append("3. Phân biệt nghiệp vụ:")
        rules_lines.extend(disamb)

    return f"\n{table}\n\n" + "\n".join(rules_lines) + "\n"


def _build_entity_section(enabled: FrozenSet[str], allow_multi_item: bool) -> str:
    sections: List[str] = ["# TRÍCH XUẤT THỰC THỂ (ENTITIES)"]
    idx = 1

    # 1. Sản phẩm / số lượng / giá
    prod_lines: List[str] = []
    if enabled & PRODUCT_INTENTS:
        prod_lines.append("   - `product`: Tên sản phẩm/hàng hóa (String hoặc null).")
    if enabled & QUANTITY_INTENTS:
        prod_lines.append(
            "   - `quantity`: Số lượng dạng số (Number hoặc null). Chỉ điền khi người dùng NÓI RÕ số lượng; "
            "KHÔNG tự đoán là 1. Số đứng NGAY TRƯỚC đơn vị tính LUÔN là `quantity`, không đưa vào price/total_price."
        )
        prod_lines.append("   - `unit`: Đơn vị tính đã chuẩn hóa (kg, lốc, thùng, cái, hộp, gói, lon, chai, ly, vỉ... hoặc null).")
    if enabled & PRICE_INTENTS:
        prod_lines.append(
            '   - `price`: Đơn giá của MỘT đơn vị (số nguyên VND, hoặc null). '
            'Chỉ điền khi gắn với 1 đơn vị ("mỗi cái 28k", "30k/kg", "20k một lon") hoặc câu không có số lượng.'
        )
        if enabled & QUANTITY_INTENTS:
            prod_lines.append(
                '   - `total_price`: TỔNG số tiền cả đơn (số nguyên VND, hoặc null). '
                'Có "hết/tổng/tất cả/thành tiền" hoặc câu có số lượng nhưng "giá X" không kèm "/đơn vị" -> total_price (price=null, không tự chia).'
            )
        if enabled & MONEY_ONLY_INTENTS:
            prod_lines.append(
                "   - Nghiệp vụ chỉ có tiền (chi_phi, thu/trả/ghi nợ tiền): số tiền BẮT BUỘC điền vào `price` (giữ nguyên dấu âm nếu có)."
            )
    if prod_lines:
        sections.append(f"{idx}. Sản phẩm, số lượng & giá:\n" + "\n".join(prod_lines))
        idx += 1

    # 2. Đối tác & thanh toán
    partner_lines: List[str] = []
    if enabled & CUSTOMER_INTENTS:
        partner_lines.append("   - `customer`: Tên hoặc cách xưng hô khách hàng (String hoặc null).")
    if enabled & SUPPLIER_INTENTS:
        partner_lines.append(
            '   - `supplier`: Tên nhà cung cấp (String hoặc null). '
            'Với `mua_hang`, người bán cho mình ("nhập từ X", "mua của X") LUÔN là `supplier`, không phải `customer`.'
        )
    partner_lines.append("   - `date`: Thời gian được nhắc tới (String hoặc null).")
    if enabled & PAYMENT_INTENTS:
        partner_lines.append(
            '   - `payment`: "tiền mặt", "chuyển khoản" hoặc công nợ: "PAID" (đã trả đủ), "PARTIAL" (trả bớt/một phần), '
            '"PENDING" (chưa trả, ghi nợ, bán chịu, mua chịu, trả sau). Không có các chữ trên -> null hoặc hình thức thanh toán.'
        )
    sections.append(f"{idx}. Đối tác & thanh toán:\n" + "\n".join(partner_lines))
    idx += 1

    # 3. Multi-item (chỉ thêm khi bật VÀ có ban_hang/mua_hang)
    if allow_multi_item and (enabled & MULTI_ITEM_INTENTS):
        sections.append(
            f"{idx}. Nhiều sản phẩm trong MỘT câu (chỉ {', '.join(sorted(enabled & MULTI_ITEM_INTENTS))}):\n"
            '   - Từ 2 mặt hàng KHÁC NHAU trở lên -> điền `items`: [{"product","quantity","unit","price","total_price"}], '
            "đặt các trường này ở cấp ngoài = null. `customer`/`supplier`/`payment`/`date` để cấp ngoài.\n"
            "   - Chỉ 1 mặt hàng -> `items` = null."
        )
        idx += 1

    # 4. Chi phí (chỉ thêm khi bật chi_phi)
    if "chi_phi" in enabled:
        sections.append(
            f"{idx}. Chi phí (`chi_phi`):\n"
            '   - `price`: Số tiền chi (số nguyên VND, bắt buộc).\n'
            '   - `category`: Tên khoản chi ngắn gọn (bỏ "thanh toán/đóng/chi", VD: "tiền điện", "lương bảo vệ"). Nghiệp vụ khác -> null.'
        )

    return "\n" + "\n\n".join(sections) + "\n"


def _build_output_section(enabled: FrozenSet[str], allow_multi_item: bool) -> str:
    fields: List[str] = []
    if enabled & PRODUCT_INTENTS:
        fields.append('    "product": "string|null"')
    if "sua_san_pham" in enabled:
        fields.append('    "new_product_name": "string|null"')
    if enabled & PRICE_INTENTS:
        fields.append('    "price": "number|null"')
    if enabled & QUANTITY_INTENTS:
        if enabled & PRICE_INTENTS:
            fields.append('    "total_price": "number|null"')
        fields.append('    "quantity": "number|null"')
        fields.append('    "unit": "string|null"')
    if enabled & CUSTOMER_INTENTS:
        fields.append('    "customer": "string|null"')
    if enabled & SUPPLIER_INTENTS:
        fields.append('    "supplier": "string|null"')
    fields.append('    "date": "string|null"')
    if enabled & PAYMENT_INTENTS:
        fields.append('    "payment": "string|null"')
    if "chi_phi" in enabled:
        fields.append('    "category": "string|null"')
    if allow_multi_item and (enabled & MULTI_ITEM_INTENTS):
        fields.append(
            '    "items": "null | [{\\"product\\":string,\\"quantity\\":number|null,\\"unit\\":string|null,\\"price\\":number|null,\\"total_price\\":number|null}]"'
        )

    fields_block = ",\n".join(fields)
    extra = (
        '\nLưu ý cho sua_san_pham: product=tên cũ, new_product_name=tên mới ("A thành B" => product=A, new_product_name=B).'
        if "sua_san_pham" in enabled
        else ""
    )
    return (
        "\nReturn JSON only:\n"
        "{\n"
        '  "status": "success|error",\n'
        '  "text": "string",\n'
        '  "intent": "string",\n'
        '  "type": "income|expense|none",\n'
        '  "entities": {\n'
        f"{fields_block}\n"
        "  },\n"
        '  "missing_fields": [],\n'
        '  "message": "string|null"\n'
        "}\n"
        f"{extra}\n"
    )


@lru_cache(maxsize=256)
def _cached_pruned_prompt(
    enabled_intents: FrozenSet[str],
    allow_multi_item: bool,
    current_date: Optional[str],
) -> str:
    intent_section = _build_intent_section(enabled_intents)
    entity_section = _build_entity_section(enabled_intents, allow_multi_item=allow_multi_item)
    output_section = _build_output_section(enabled_intents, allow_multi_item=allow_multi_item)

    prompt = (
        "You are an AI for Vietnamese transaction logging. Parse Speech-to-Text inputs into JSON.\n"
        f"{COMMON_RULES}"
        f"{intent_section}"
        f"{entity_section}"
        f"{output_section}"
    ).strip()
    if current_date:
        prompt += f"\nSystem Date: {current_date}."
    return prompt


def build_pruned_system_prompt(
    allowed_intents: Iterable[str],
    allow_multi_item: bool = True,
    current_date: Optional[str] = None,
) -> str:
    """
    Dựng system prompt rút gọn chỉ chứa đúng các intent trong `allowed_intents`.
    Các tên không hợp lệ được lọc bỏ; kết quả được cache theo bộ (intents, allow_multi_item, current_date).
    """
    valid = frozenset(i for i in allowed_intents if i in INTENT_TABLE_ROWS)
    return _cached_pruned_prompt(valid, bool(allow_multi_item), current_date)


def estimate_prompt_stats(
    full_prompt: str,
    active_prompt: str,
) -> Dict[str, float]:
    """
    Ước lượng độ dài & mức tiết kiệm token (tiếng Việt trung bình ~3.5 ký tự/token).
    Dùng cho màn hình Admin để quan sát trực quan hiệu quả tối ưu của từng gói.
    """
    full_chars = len(full_prompt)
    active_chars = len(active_prompt)
    full_tokens = max(1, round(full_chars / 3.5))
    active_tokens = round(active_chars / 3.5) if active_chars > 0 else 0
    saved_pct = round(((full_chars - active_chars) / full_chars) * 100.0, 1) if full_chars > 0 else 0.0
    return {
        "full_prompt_chars": full_chars,
        "active_prompt_chars": active_chars,
        "estimated_full_tokens": full_tokens,
        "estimated_active_tokens": active_tokens,
        "saved_percent": max(0.0, saved_pct),
    }
