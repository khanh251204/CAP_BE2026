"""
Tiền xử lý ảnh hóa đơn / phiếu trước khi OCR.

- quality_check: cổng chất lượng (mờ, tối, cháy sáng, phân giải thấp). Backend kiểm tra lại dù app đã chặn.
- prepare: sửa hướng EXIF -> (tuỳ chọn) khoanh vùng tờ phiếu + nắn phẳng -> thu nhỏ cạnh dài.

Không nhị phân hóa ảnh: Vintern được huấn luyện trên ảnh màu tự nhiên.
cv2 / Pillow chỉ import khi gọi hàm, để server vẫn khởi động được khi chưa cài gói OCR.
"""
from io import BytesIO
from typing import Dict, Tuple

MAX_SIDE = 1800

BLUR_MIN = 60.0          # phương sai Laplacian (ảnh đưa về cạnh dài 1000 px)
BRIGHT_MIN = 100.0       # độ sáng trung bình 0-255; giấy phiếu bình thường ~180-230
CLIPPED_MAX = 0.5        # tỉ lệ điểm ảnh cháy sáng (>= 252) tối đa
LONG_SIDE_MIN = 800      # ảnh chụp bằng điện thoại thường > 1500 px

# Lý do chặn -> câu nhắc người dùng
REASON_MESSAGES = {
    "blur": "Ảnh bị mờ, bạn giữ chắc tay và chụp lại nhé.",
    "dark": "Ảnh quá tối, bạn chụp ở nơi nhiều sáng hơn nhé.",
    "overexposed": "Ảnh bị cháy sáng, bạn tránh ánh đèn chiếu thẳng vào giấy nhé.",
    "low_resolution": "Ảnh độ phân giải thấp, bạn chụp gần hơn hoặc dùng ảnh gốc nhé.",
}


class InvalidImageError(ValueError):
    """Dữ liệu tải lên không phải ảnh đọc được."""


def load_image(data: bytes):
    from PIL import Image, ImageOps, UnidentifiedImageError
    try:
        img = Image.open(BytesIO(data))
        img = ImageOps.exif_transpose(img)
        return img.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as e:
        raise InvalidImageError("Tệp tải lên không phải ảnh hợp lệ") from e


def _to_bgr(img):
    import cv2
    import numpy as np
    return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)


def _to_pil(bgr):
    import cv2
    from PIL import Image
    return Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))


def quality_check(img) -> Dict:
    """Đo độ mờ, độ sáng, độ phân giải. ok=False thì yêu cầu chụp lại."""
    import cv2
    bgr = _to_bgr(img)
    h, w = bgr.shape[:2]
    scale = 1000.0 / max(h, w)
    small = cv2.resize(bgr, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    bright = float(gray.mean())
    clipped = float((gray >= 252).mean())
    reasons = []
    if blur < BLUR_MIN:
        reasons.append("blur")
    if bright < BRIGHT_MIN:
        reasons.append("dark")
    if clipped > CLIPPED_MAX:
        reasons.append("overexposed")
    if max(h, w) < LONG_SIDE_MIN:
        reasons.append("low_resolution")
    return {
        "ok": not reasons,
        "reasons": reasons,
        "messages": [REASON_MESSAGES[r] for r in reasons],
        "blur": round(blur, 1),
        "brightness": round(bright, 1),
        "clipped": round(clipped, 3),
        "size": [w, h],
    }


def resize_long_side(img, max_side: int = MAX_SIDE):
    from PIL import Image
    w, h = img.size
    long_side = max(w, h)
    if long_side <= max_side:
        return img
    s = max_side / long_side
    return img.resize((int(w * s), int(h * s)), Image.LANCZOS)


def _order_corners(pts):
    """Sắp 4 góc: trên-trái, trên-phải, dưới-phải, dưới-trái."""
    import numpy as np
    s, d = pts.sum(axis=1), np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]], dtype=np.float32)


def crop_document(img, min_area: float = 0.15) -> Tuple[object, bool]:
    """
    Khoanh vùng tờ phiếu (giấy sáng, ít màu) và nắn phẳng.
    Trả (ảnh, có tìm được khung không). Không tìm được thì trả nguyên ảnh, nên không bao giờ làm mất ảnh.
    """
    import cv2
    import numpy as np
    bgr = _to_bgr(img)
    h, w = bgr.shape[:2]
    scale = 1000.0 / max(h, w)
    small = cv2.resize(bgr, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(cv2.GaussianBlur(small, (5, 5), 0), cv2.COLOR_BGR2HSV)
    mask = ((hsv[..., 1] < 55) & (hsv[..., 2] > 140)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (41, 41)))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return img, False
    cnt = cv2.convexHull(max(contours, key=cv2.contourArea))
    frame_area = small.shape[0] * small.shape[1]
    area = cv2.contourArea(cnt)
    if area < min_area * frame_area or area > 0.97 * frame_area:
        return img, False
    approx = cv2.approxPolyDP(cnt, 0.02 * cv2.arcLength(cnt, True), True)
    quad = approx.reshape(-1, 2) if len(approx) == 4 else cv2.boxPoints(cv2.minAreaRect(cnt))
    src = _order_corners(np.asarray(quad, dtype=np.float32)) / scale
    tl, tr, br, bl = src
    out_w = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    out_h = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    if out_w < 100 or out_h < 100:
        return img, False
    dst = np.array([[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]], dtype=np.float32)
    warped = cv2.warpPerspective(bgr, cv2.getPerspectiveTransform(src, dst), (out_w, out_h))
    return _to_pil(warped), True


def prepare(data: bytes, crop: bool = False) -> Tuple[object, Dict]:
    """Đọc ảnh, đo chất lượng trên ảnh gốc, rồi trả (ảnh đã xử lý, báo cáo chất lượng)."""
    img = load_image(data)
    quality = quality_check(img)
    if crop:
        img, found = crop_document(img)
        quality["crop_found"] = found
    return resize_long_side(img), quality
