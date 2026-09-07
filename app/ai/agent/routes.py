# ============================================================
# INTENT → MCP TOOL
# ============================================================

ROUTES = {

    # =========================
    # GIAO DỊCH
    # =========================

    "ban_hang": "export_inventory",
    "nhap_hang": "import_inventory",
    "kiem_kho": "check_stock",

    # =========================
    # PRODUCT
    # =========================

    "tim_san_pham": "search_products",
    "xem_san_pham": "search_products",

    # =========================
    # CÔNG NỢ KHÁCH
    # =========================

    "ghi_no_khach_hang": "ghi_no_khach_hang",
    "thu_no_khach_hang": "thu_no_khach_hang",
    "khach_ghi_no": "ghi_no_khach_hang",
    "thu_no_khach": "thu_no_khach_hang",

    # =========================
    # CÔNG NỢ NHÀ CUNG CẤP
    # =========================

    "ghi_no_nha_cung_cap": "ghi_no_nha_cung_cap",
    "ncc_ghi_no": "ghi_no_nha_cung_cap",
    "thu_no_nha_cung_cap": "thu_no_nha_cung_cap",
    "tra_no_nha_cung_cap": "thu_no_nha_cung_cap",
    "tra_no_ncc": "thu_no_nha_cung_cap",

    # =========================
    # CHI PHÍ / HÀNG HỎNG
    # =========================

    "chi_phi": "create_expense",
    "hang_hong": "create_damaged_goods",

    # =========================
    # BÁO CÁO
    # =========================

    "bao_cao": "get_transaction_report"
}


# ============================================================
# REQUIRED FIELDS
# ============================================================

REQUIRED_FIELDS = {

    "them_san_pham": [
        "product",
        "price"
    ],

    "sua_san_pham": [
        "product"
    ],

    "xoa_san_pham": [
        "product"
    ],

    "kiem_kho": [
        "product"
    ],

    "ban_hang": [
        "product",
        "quantity",
        "unit"
    ],

    "nhap_hang": [
        "product",
        "price",
        "quantity",
        "unit"
    ],

    "ghi_no_khach_hang": [
        "customer"
    ],

    "thu_no_khach_hang": [
        "customer",
        "price"
    ],

    "khach_ghi_no": [
        "customer"
    ],

    "thu_no_khach": [
        "customer",
        "price",
        "payment"
    ],

    "ghi_no_nha_cung_cap": [
        "supplier"
    ],

    "ncc_ghi_no": [
        "supplier"
    ],

    "thu_no_nha_cung_cap": [
        "supplier"
    ],

    "tra_no_nha_cung_cap": [
        "supplier"
    ],

    "tra_no_ncc": [
        "supplier"
    ],

    "chi_phi": [
        "price"
    ],

    "hang_hong": [
        "price"
    ]
}
