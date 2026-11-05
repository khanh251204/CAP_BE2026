"""Vòng cải thiện AI từ Data Lake (Capstone 2).

Script chỉ ĐỌC data_lake/ và GHI file ra data_lake/dataset/. Không đụng DB,
không tự sửa prompt / từ điển. Con người duyệt ở bước `candidates`.

Lệnh:
  clean       Kiểm tra chất lượng toàn Data Lake (chỉ báo cáo, không xóa gì)
  report      Thống kê lỗi từ feedback/correction (tỉ lệ sửa, trường sai nhiều...)
  candidates  Xuất các ca bị sửa ra dataset/review/ để người duyệt (cột approved)
  dict        Gợi ý từ cần thêm vào normalization_data.json (dataset/review/)
  testset     Ca đã duyệt + qua kiểm tra định dạng -> dataset/gold/ (bộ test mới)
  finetune    Ca đã duyệt + qua kiểm tra -> dataset/gold/ JSONL (đã ẩn tên, SĐT)

Tầng dataset: review/ = chờ duyệt, gold/ = đã duyệt và đạt chuẩn.

Ví dụ:
  PYTHONIOENCODING=utf-8 ./.venv/Scripts/python.exe scripts/datalake_improve.py report
"""
import argparse
import csv
import glob
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime

# Ánh xạ intent trong Data Lake -> (intent, type) của bộ test evaluation/
EVAL_INTENT = {
    "ban_hang": ("bán_hàng", "sale"),
    "mua_hang": ("nhập_hàng", "purchase"),
    "nhap_hang": ("nhập_hàng", "purchase"),
    "chi_phi": ("chi_phi", "expense"),
    "chi_tien": ("chi_phi", "expense"),
}

# final_transaction -> cột CSV evaluation
FIELD_TO_COL = {
    "product_name": "product",
    "unit_price": "price",
    "quantity": "quantity",
    "unit": "unit",
    "customer_name": "customer",
    "supplier_name": "supplier",
    "date": "date",
}

EVAL_COLUMNS = [
    "id", "text", "business_type", "intent", "type", "product", "new_product_name",
    "price", "quantity", "unit", "customer", "supplier", "date", "payment",
    "missing_fields", "message",
]
CAND_COLUMNS = ["approved", "voice_id", "business_type", "intent", "flag",
                "changed_fields", "text"] + [c for c in EVAL_COLUMNS if c not in
                ("id", "text", "business_type", "intent", "message")]


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def load_corrections(lake, include_short=False):
    """Feedback đầy đủ có ai_result + final_transaction.
    include_short=True: trả thêm bản rút gọn (chỉ có correction.ai / correction.correction)."""
    full, short = [], []
    for p in sorted(glob.glob(os.path.join(lake, "feedback", "correction", "*", "*.json"))):
        d = _read_json(p)
        if not isinstance(d, dict):
            continue
        if isinstance(d.get("ai_result"), dict) and isinstance(d.get("final_transaction"), dict):
            full.append(d)
        elif isinstance(d.get("correction"), dict):
            short.append(d)
    return (full, short) if include_short else full


# Tên trường trong correction.ai rút gọn -> tên trường chuẩn
SHORT_FIELD = {"price": "unit_price", "product": "product_name", "customer": "customer_name",
               "supplier": "supplier_name"}


def load_raw_users(lake):
    users = {}
    for p in glob.glob(os.path.join(lake, "raw", "voice", "*", "*.json")):
        d = _read_json(p)
        if isinstance(d, dict):
            users[d.get("voice_record_id")] = d.get("user_id")
    return users


def load_ai_results(lake):
    res = {}
    for p in glob.glob(os.path.join(lake, "processed", "ai_result", "*", "*.json")):
        d = _read_json(p)
        if isinstance(d, dict) and d.get("voice_record_id") is not None:
            res[d["voice_record_id"]] = d
    return res


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# Cách nói về thanh toán -> enum ERD. Dùng để không coi "tiền mặt" -> PAID là một lần sửa.
PAYMENT_EQUIV = {
    "tiền mặt": "PAID", "chuyển khoản": "PAID", "trả đủ": "PAID", "đã trả": "PAID",
    "trả hết": "PAID", "completed": "PAID", "cash": "PAID",
    "nợ": "PENDING", "ghi nợ": "PENDING", "chưa trả": "PENDING", "mua chịu": "PENDING",
    "trả một phần": "PARTIAL", "trả trước": "PARTIAL",
}


def norm_payment(v):
    if v in (None, ""):
        return None
    t = str(v).strip().lower()
    return PAYMENT_EQUIV.get(t, t.upper())


def payment_change(ai, final):
    """(thay_doi_that, sua_gia). sua_gia = khác chuỗi nhưng cùng nghĩa."""
    a, b = ai.get("payment_status"), final.get("payment_status")
    if a in (None, "") or b in (None, ""):
        return False, False
    if str(a).strip().lower() == str(b).strip().lower():
        return False, False
    if norm_payment(a) == norm_payment(b):
        return False, True
    return True, False


def changed_fields(ai, final):
    """Các trường người dùng đã sửa so với bản AI đề xuất (đã bỏ khác biệt chỉ do định dạng)."""
    changed = {}
    real_pay, _ = payment_change(ai, final)
    if real_pay:
        changed["payment_status"] = (ai.get("payment_status"), final.get("payment_status"))
    for k in FIELD_TO_COL:
        a, b = ai.get(k), final.get(k)
        if a in (None, "") and b in (None, ""):
            continue
        na, nb = _num(a), _num(b)
        same = (na == nb) if (na is not None and nb is not None) else (str(a).strip().lower() == str(b).strip().lower())
        if not same:
            changed[k] = (a, b)
    return changed


def flag_of(changes):
    """Gắn cờ gợi ý để người duyệt biết ca nào đáng chú ý."""
    for k in ("unit_price", "quantity"):
        if k in changes:
            a, b = _num(changes[k][0]), _num(changes[k][1])
            if a and b:
                r = max(a, b) / min(a, b)
                if r in (10, 100, 1000):
                    return f"{k}_x{int(r)}"  # nhiều khả năng nghe sai số/đơn vị tiền
    if "product_name" in changes:
        return "product_changed"
    return ""


def get_intent(corr, ai_results):
    rec = ai_results.get(corr.get("voice_record_id")) or {}
    return rec.get("intent") or ""


def get_text(corr, ai_results):
    rec = ai_results.get(corr.get("voice_record_id")) or {}
    return (corr["ai_result"].get("input_text") or rec.get("transcript") or "").strip()



def review_dir(lake):
    return os.path.join(lake, "dataset", "review")


def gold_dir(lake):
    return os.path.join(lake, "dataset", "gold")


VALID_INTENTS = {v[0] for v in EVAL_INTENT.values()}
MAX_PRICE = 1_000_000_000
MAX_QTY = 1_000_000
PHONE = re.compile(r"\b0\d{8,10}\b")


def validate_row(row):
    """Cổng chất lượng trước khi vào Gold. Trả về danh sách lỗi (rỗng = đạt)."""
    errs = []
    if not str(row.get("text", "")).strip():
        errs.append("thiếu câu gốc")
    if row.get("intent") not in VALID_INTENTS:
        errs.append("intent không hợp lệ")
    if row.get("intent") in ("bán_hàng", "nhập_hàng") and not str(row.get("product", "")).strip():
        errs.append("thiếu sản phẩm")
    for col, hi in (("quantity", MAX_QTY), ("price", MAX_PRICE)):
        v = row.get(col)
        if v not in (None, ""):
            n = _num(v)
            if n is None or n <= 0 or n > hi:
                errs.append(f"{col} không hợp lệ")
    return errs


def load_benchmark_texts(path):
    """Câu trong benchmark cố định: không được đưa vào dữ liệu fine-tune."""
    if not path or not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["text"].strip().lower() for r in csv.DictReader(f)}


# ----------------------------------------------------------------- clean
def cmd_clean(args):
    lake = args.lake
    raw, proc, fb = {}, {}, []
    bad_json = 0
    for zone, store in (("raw/voice", raw), ("processed/ai_result", proc)):
        for p in glob.glob(os.path.join(lake, *zone.split("/"), "*", "*.json")):
            d = _read_json(p)
            if not isinstance(d, dict):
                bad_json += 1
                continue
            store[d.get("voice_record_id")] = d
    for p in glob.glob(os.path.join(lake, "feedback", "correction", "*", "*.json")):
        d = _read_json(p)
        if isinstance(d, dict):
            fb.append(d)
        else:
            bad_json += 1

    issues = Counter()
    seen = Counter()
    for d in proc.values():
        t = (d.get("transcript") or "").strip()
        if not t:
            issues["processed: thiếu transcript"] += 1
        else:
            seen[(raw.get(d.get("voice_record_id"), {}).get("user_id"), t.lower())] += 1
            if len(t.split()) < 2:
                issues["processed: transcript quá ngắn (<2 từ)"] += 1
            if PHONE.search(t):
                issues["processed: transcript có số điện thoại (cần ẩn)"] += 1
        if not d.get("intent"):
            issues["processed: thiếu intent"] += 1
        if d.get("confidence") is None:
            issues["processed: confidence null (không lọc được theo độ tin cậy)"] += 1
        if d.get("status") == "PROCESSING":
            issues["processed: PROCESSING (phân tích xong nhưng người dùng chưa/không xác nhận)"] += 1
        elif d.get("status") not in (None, "SUCCESS"):
            issues["processed: status " + str(d.get("status"))] += 1
    issues["processed: câu trùng (cùng user, cùng nội dung)"] += sum(n - 1 for n in seen.values() if n > 1)
    for d in raw.values():
        if not d.get("audio_path"):
            issues["raw: thiếu audio_path"] += 1
    issues["voice có raw nhưng chưa có processed"] += len(set(raw) - set(proc))
    issues["voice có processed nhưng thiếu raw"] += len(set(proc) - set(raw))
    for d in fb:
        if not isinstance(d.get("ai_result"), dict):
            issues["feedback: dạng rút gọn, mất ai_result/final_transaction"] += 1
        elif isinstance(d.get("final_transaction"), dict):
            if not changed_fields(d["ai_result"], d["final_transaction"]) and \
                    payment_change(d["ai_result"], d["final_transaction"])[1]:
                issues["feedback: sửa giả (chỉ khác định dạng thanh toán)"] += 1
        if not d.get("correction_type"):
            issues["feedback: thiếu correction_type"] += 1
        if not d.get("voice_record_id"):
            issues["feedback: thiếu voice_record_id"] += 1
        elif d.get("voice_record_id") not in proc:
            issues["feedback: không tìm thấy processed tương ứng"] += 1

    # Zone dataset/<ngày>/ do DataLakeService ghi: phải khớp với processed SUCCESS
    ds_ids = set()
    for p in glob.glob(os.path.join(lake, "dataset", "20*", "*.json")):
        d = _read_json(p)
        if isinstance(d, dict):
            ds_ids.add(d.get("voice_record_id"))
    ok_ids = {k for k, d in proc.items() if d.get("status") == "SUCCESS"}
    issues["dataset: có mẫu nhưng processed không phải SUCCESS"] += len(ds_ids - ok_ids)
    issues["dataset: processed SUCCESS nhưng thiếu mẫu dataset"] += len(ok_ids - ds_ids)

    print(f"Raw: {len(raw)} | Processed: {len(proc)} (SUCCESS {len(ok_ids)}) | Dataset: {len(ds_ids)} | "
          f"Feedback: {len(fb)} | file JSON lỗi: {bad_json}")
    print("\nVấn đề phát hiện (chỉ báo cáo, không xóa gì):")
    found = False
    for k, v in sorted(issues.items(), key=lambda x: -x[1]):
        if v:
            found = True
            print(f"  {v:>5}  {k}")
    if not found:
        print("  không có")


# ---------------------------------------------------------------- report
def cmd_report(args):
    corrs, short = load_corrections(args.lake, include_short=True)
    ai = load_ai_results(args.lake)
    confirmed = sum(1 for d in ai.values() if d.get("status") == "SUCCESS")
    total_fb = len(corrs) + len(short)
    print(f"Feedback: {total_fb} (đầy đủ {len(corrs)}, rút gọn {len(short)}) | "
          f"AI result: {len(ai)} (đã xác nhận {confirmed})")
    if confirmed:
        print(f"Tỉ lệ bị sửa trên giao dịch đã xác nhận (xấp xỉ): {total_fb / confirmed:.1%}")
    field_cnt, type_cnt, intent_cnt, flag_cnt = Counter(), Counter(), Counter(), Counter()
    for d in short:
        field_cnt.update(SHORT_FIELD.get(k, k) for k in (d["correction"].get("ai") or {}))
        type_cnt["(rút gọn, không rõ loại)"] += 1
        intent_cnt[get_intent(d, ai) or "(không rõ)"] += 1
    fake = 0
    for c in corrs:
        ch = changed_fields(c["ai_result"], c["final_transaction"])
        if not ch and payment_change(c["ai_result"], c["final_transaction"])[1]:
            fake += 1
        field_cnt.update(ch.keys())
        type_cnt[c.get("correction_type") or "(không rõ)"] += 1
        intent_cnt[get_intent(c, ai) or "(không rõ)"] += 1
        if flag_of(ch):
            flag_cnt[flag_of(ch)] += 1
    real = total_fb - fake
    print(f"Sửa giả (chỉ khác định dạng, vd 'tiền mặt' -> PAID): {fake} -> sửa thật: {real}")
    if confirmed:
        print(f"Tỉ lệ sửa thật trên giao dịch đã xác nhận (xấp xỉ): {real / confirmed:.1%}")
    for title, cnt in (("Trường bị sửa nhiều nhất", field_cnt), ("Loại sửa", type_cnt),
                       ("Intent bị sửa", intent_cnt), ("Cờ đáng chú ý", flag_cnt)):
        print(f"\n{title}:")
        for k, v in cnt.most_common():
            print(f"  {k}: {v}")


# ------------------------------------------------------------ candidates
def build_candidates(lake):
    ai_results = load_ai_results(lake)
    rows, skipped = [], Counter()
    _, short = load_corrections(lake, include_short=True)
    if short:
        skipped["feedback rút gọn (thiếu ai_result/final_transaction)"] += len(short)
    for c in load_corrections(lake):
        intent_raw = get_intent(c, ai_results)
        text = get_text(c, ai_results)
        if not intent_raw:
            skipped["không xác định được intent (thiếu voice_record_id hoặc processed)"] += 1
            continue
        if intent_raw not in EVAL_INTENT:
            skipped[f"intent {intent_raw} chưa hỗ trợ trong bộ test"] += 1
            continue
        if not text:
            skipped["thiếu câu gốc"] += 1
            continue
        ch = changed_fields(c["ai_result"], c["final_transaction"])
        if not ch:
            if payment_change(c["ai_result"], c["final_transaction"])[1]:
                skipped["sửa giả (chỉ khác định dạng thanh toán)"] += 1
            else:
                skipped["không có trường nào đổi"] += 1
            continue
        intent, typ = EVAL_INTENT[intent_raw]
        final = c["final_transaction"]
        row = {col: "" for col in CAND_COLUMNS}
        row.update({
            "approved": "", "voice_id": c.get("voice_record_id") or "",
            "business_type": "", "intent": intent, "flag": flag_of(ch),
            "changed_fields": ",".join(ch.keys()), "text": text, "type": typ,
        })
        for field, col in FIELD_TO_COL.items():
            v = final.get(field)
            if v is not None and col in row:
                if isinstance(v, float) and v.is_integer():
                    v = int(v)
                row[col] = v
        if "payment_status" in ch:
            row["payment"] = norm_payment(final.get("payment_status")) or ""
        rows.append(row)
    return rows, skipped


def _write_csv(path, columns, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def cmd_candidates(args):
    rows, skipped = build_candidates(args.lake)
    out = args.out or os.path.join(review_dir(args.lake), "candidates.csv")
    _write_csv(out, CAND_COLUMNS, rows)
    print(f"Đã xuất {len(rows)} ca ra {out}")
    for k, v in skipped.items():
        print(f"  bỏ qua {v} ca: {k}")
    print("Bước tiếp: mở file, điền approved=1 cho ca ĐÚNG (và business_type nếu muốn), "
          "xóa/để trống ca người dùng nhập nhầm.")


# ------------------------------------------------------------------ dict
def cmd_dict(args):
    cnt = Counter()
    for c in load_corrections(args.lake):
        for field in ("unit", "product_name"):
            a, b = c["ai_result"].get(field), c["final_transaction"].get(field)
            if a and b and str(a).strip().lower() != str(b).strip().lower():
                cnt[(field, str(a).strip().lower(), str(b).strip().lower())] += 1
    out = args.out or os.path.join(review_dir(args.lake), "dict_suggestions.csv")
    rows = [{"type": "unit" if f == "unit" else "product", "ai_hieu": a,
             "nguoi_dung_sua_thanh": b, "so_lan": n, "approved": ""}
            for (f, a, b), n in cnt.most_common()]
    _write_csv(out, ["type", "ai_hieu", "nguoi_dung_sua_thanh", "so_lan", "approved"], rows)
    print(f"Đã xuất {len(rows)} gợi ý ra {out}")
    print("Chỉ thêm vào app/ai/rag/knowledge/normalization_data.json những dòng lặp lại "
          "nhiều lần và bạn đã kiểm tra tay.")


# --------------------------------------------------------------- helpers
def _approved_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f) if str(r.get("approved", "")).strip() == "1"]


# --------------------------------------------------------------- testset
def cmd_testset(args):
    base = list(csv.DictReader(open(args.base, encoding="utf-8-sig", newline="")))
    approved = _approved_rows(args.candidates)
    if not approved:
        print("Chưa có ca nào approved=1 trong file candidates.")
        return
    seen = {r["text"].strip().lower() for r in base}
    rejected = Counter()
    next_id = max((int(r["id"]) for r in base if str(r["id"]).isdigit()), default=0) + 1
    added = 0
    for a in approved:
        errs = validate_row(a)
        if errs:
            for e in errs:
                rejected[e] += 1
            continue
        if a["text"].strip().lower() in seen:
            continue
        row = {c: a.get(c, "") for c in EVAL_COLUMNS}
        row["id"] = next_id
        row["business_type"] = a.get("business_type") or "PRODUCER"
        next_id += 1
        base.append(row)
        seen.add(a["text"].strip().lower())
        added += 1
    out = args.out or os.path.join(gold_dir(args.lake), "testset_merged.csv")
    _write_csv(out, EVAL_COLUMNS, base)
    print(f"Thêm {added} ca mới (bỏ trùng). Bộ test mới: {out} ({len(base)} dòng)")
    for k, v in rejected.items():
        print(f"  loại {v} ca: {k}")
    print(f"Chạy: python -m evaluation.run_evaluation --csv {out}")


# -------------------------------------------------------------- finetune
def _mask(text, names):
    for n in sorted({n for n in names if n}, key=len, reverse=True):
        text = re.sub(re.escape(n), "<TEN>", text, flags=re.I)
    return PHONE.sub("<SDT>", text)


def cmd_finetune(args):
    approved = _approved_rows(args.candidates)
    out = args.out or os.path.join(gold_dir(args.lake),
                                   f"finetune_{datetime.now():%Y%m%d}.jsonl")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bench = load_benchmark_texts(args.benchmark)
    n, rejected = 0, Counter()
    with open(out, "w", encoding="utf-8") as f:
        for a in approved:
            errs = validate_row(a)
            if a["text"].strip().lower() in bench:
                errs.append("trùng benchmark cố định")
            if errs:
                for e in errs:
                    rejected[e] += 1
                continue
            names = [a.get("customer"), a.get("supplier")]
            ents = {k: a.get(k) for k in ("product", "quantity", "unit", "price", "date")
                    if a.get(k) not in (None, "")}
            ents.update({k: "<TEN>" for k in ("customer", "supplier") if a.get(k)})
            f.write(json.dumps({"text": _mask(a["text"], names), "intent": a["intent"],
                                "entities": ents}, ensure_ascii=False) + "\n")
            n += 1
    print(f"Đã xuất {n} mẫu fine-tune ra {out} (tên, SĐT đã ẩn)")
    for k, v in rejected.items():
        print(f"  loại {v} ca: {k}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lake", default=os.getenv("DATA_LAKE_PATH", "data_lake"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("clean", cmd_clean), ("report", cmd_report), ("candidates", cmd_candidates), ("dict", cmd_dict),
                     ("testset", cmd_testset), ("finetune", cmd_finetune)):
        p = sub.add_parser(name)
        p.set_defaults(fn=fn)
        if name not in ("report", "clean"):
            p.add_argument("--out")
        if name in ("testset", "finetune"):
            p.add_argument("--candidates", default=None)
        if name == "testset":
            p.add_argument("--base", default="evaluation/voicecash_producer_1000.csv")
        if name == "finetune":
            p.add_argument("--benchmark", default="evaluation/voicecash_producer_1000.csv")
    args = ap.parse_args()
    if getattr(args, "candidates", "x") is None:
        args.candidates = os.path.join(review_dir(args.lake), "candidates.csv")
    args.fn(args)


if __name__ == "__main__":
    main()
