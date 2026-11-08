"""AI Monitoring: người dùng sửa bản nháp của AI bao nhiêu lần, ở lệnh nào, sửa trường nào."""
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.user_correction_model import UserCorrection
from app.models.voice_record_model import VoiceRecord

# Tên lệnh cũ / bí danh gộp về một tên để thống kê không bị tách đôi
INTENT_ALIASES = {
    "nhap_hang": "mua_hang",
    "chi_tien": "chi_phi",
    "ghi_no_khach_hang": "khach_ghi_no",
    "thu_no_khach_hang": "thu_no_khach",
    "ncc_ghi_no": "ghi_no_nha_cung_cap",
    "tra_no_ncc": "tra_no_nha_cung_cap",
    "thu_no_nha_cung_cap": "tra_no_nha_cung_cap",
    "xem_san_pham": "tim_san_pham",
    "ghi_no_ncc": "ghi_no_nha_cung_cap",
}
UNKNOWN_INTENT = "khong_ro"


def canonical_intent(name: Optional[str]) -> str:
    n = str(name or "").strip().lower()
    if not n:
        return UNKNOWN_INTENT
    return INTENT_ALIASES.get(n, n)


def _rate(corrected: int, confirmed: int) -> float:
    return round(corrected * 100.0 / confirmed, 2) if confirmed else 0.0


class AdminAiMonitoringService:
    @staticmethod
    def correction_rate_by_intent(
        db: Session,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        top_fields: int = 3,
    ) -> Dict[str, Any]:
        """
        Tỉ lệ sửa = số bản ghi giọng nói / câu lệnh ĐÃ GHI SỔ (SUCCESS) mà người dùng đã hiệu chỉnh
        trên màn Xác nhận, chia cho tổng số đã ghi sổ, theo từng lệnh (intent).
        - Mẫu số: Voice_Record status SUCCESS trong khoảng thời gian.
        - Tử số: số Voice_Record khác nhau có bản ghi User_Correction.
        - failed: bản ghi bị từ chối / lỗi (không vào tỉ lệ sửa).
        - top_corrected_fields: các trường (product, quantity, price...) bị sửa nhiều nhất của lệnh đó.
        """
        vr = db.query(VoiceRecord.voice_id, VoiceRecord.intent, VoiceRecord.status)
        if date_from:
            vr = vr.filter(VoiceRecord.created_at >= date_from)
        if date_to:
            vr = vr.filter(VoiceRecord.created_at <= date_to)
        records = vr.all()

        confirmed: Counter = Counter()
        failed: Counter = Counter()
        intent_of: Dict[int, str] = {}
        for voice_id, intent, status in records:
            name = canonical_intent(intent)
            intent_of[voice_id] = name
            st = str(status or "").upper()
            if st == "SUCCESS":
                confirmed[name] += 1
            elif st == "FAILED":
                failed[name] += 1

        corr = db.query(UserCorrection.voice_record_id, UserCorrection.diff)
        if date_from:
            corr = corr.filter(UserCorrection.created_at >= date_from)
        if date_to:
            corr = corr.filter(UserCorrection.created_at <= date_to)

        corrected_records: Dict[str, set] = defaultdict(set)
        fields: Dict[str, Counter] = defaultdict(Counter)
        without_voice = 0
        for voice_id, diff in corr.all():
            if voice_id is None or voice_id not in intent_of:
                without_voice += 1
                continue
            name = intent_of[voice_id]
            corrected_records[name].add(voice_id)
            ai_side = (diff or {}).get("ai") if isinstance(diff, dict) else None
            for key in (ai_side or {}):
                fields[name][key] += 1

        names = sorted(set(confirmed) | set(failed) | set(corrected_records))
        by_intent: List[Dict[str, Any]] = []
        for n in names:
            c = len(corrected_records.get(n, ()))
            by_intent.append({
                "intent": n,
                "confirmed": confirmed[n],
                "corrected": c,
                "correction_rate": _rate(c, confirmed[n]),
                "failed": failed[n],
                "top_corrected_fields": [{"field": f, "count": k} for f, k in fields[n].most_common(top_fields)],
            })
        # Lệnh bị sửa nhiều (theo tỉ lệ, rồi theo số lượng) lên đầu
        by_intent.sort(key=lambda r: (-r["correction_rate"], -r["confirmed"], r["intent"]))

        total_confirmed = sum(confirmed.values())
        total_corrected = sum(len(v) for v in corrected_records.values())
        return {
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "totals": {
                "confirmed": total_confirmed,
                "corrected": total_corrected,
                "correction_rate": _rate(total_corrected, total_confirmed),
                "failed": sum(failed.values()),
                "corrections_without_voice_record": without_voice,
            },
            "by_intent": by_intent,
        }
