"""
Engine OCR Vintern-1B-v3.5 (InternVL: InternViT-300M + Qwen2.5-0.5B), chạy trong tiến trình API.

- Nạp lười ở lần gọi đầu (tải ~2 GB từ Hugging Face), giữ một bản duy nhất; khóa lại để mỗi lúc chỉ một ảnh chạy.
- CPU nạp fp32 (~4 GB RAM), GPU nạp bf16. Một ảnh mất vài chục giây trên CPU, nên route chạy trong thread riêng.
- Mã của Vintern chỉ chạy với transformers 4.44.x, còn .venv dùng 5.x (lỗi all_tied_weights_keys): bản 4.44.2
  cài riêng vào thư mục OCR_DEPS_DIR và được ưu tiên khi nạp model (xem requirements-ocr.txt).
Engine chỉ làm ảnh -> văn bản; mọi quyết định nghiệp vụ nằm ở backend.
"""
import logging
import os
import sys
import threading
import time
from typing import Dict

from app.ai.ocr.text_utils import collapse_repeats

logger = logging.getLogger(__name__)

OCR_PROMPT = (
    "<image>\nChép lại nguyên văn toàn bộ chữ trong ảnh, từng dòng một đúng như trên hóa đơn, "
    "kể cả mã số và số tiền. Không giải thích, không tóm tắt, không dùng markdown."
)

_MEAN = (0.485, 0.456, 0.406)
_STD = (0.229, 0.224, 0.225)
TILE = 448


class OcrUnavailableError(RuntimeError):
    """Chưa cài gói OCR hoặc không nạp được model."""


_BE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _use_ocr_deps(deps_dir: str) -> None:
    """
    Đưa thư mục chứa transformers 4.44.x lên đầu sys.path trước khi import.
    Chỉ có tác dụng khi transformers chưa được import trong tiến trình (server không import sẵn,
    trừ chế độ ACTIVE_AI_MODEL=qwen_local).
    """
    loaded = sys.modules.get("transformers")
    if loaded is not None:
        version = getattr(loaded, "__version__", "?")
        if not version.startswith("4."):
            raise OcrUnavailableError(
                f"transformers {version} đã được nạp trước trong tiến trình; Vintern cần 4.44.x "
                "(tắt ACTIVE_AI_MODEL=qwen_local hoặc chạy OCR ở tiến trình riêng)")
        return
    candidates = [deps_dir, os.path.join("ocr_benchmark", ".deps")]
    for d in candidates:
        path = d if os.path.isabs(d) else os.path.join(_BE_ROOT, d)
        if os.path.isdir(os.path.join(path, "transformers")):
            if path not in sys.path:
                sys.path.insert(0, path)
            logger.info("[OCR] Dùng transformers từ %s", path)
            return
    logger.warning("[OCR] Không thấy thư mục OCR_DEPS_DIR, dùng transformers của môi trường hiện tại")


class VinternEngine:
    def __init__(self, model_id: str, max_tiles: int = 2, max_new_tokens: int = 768, deps_dir: str = ".ocr_deps"):
        self.model_id = model_id
        self.deps_dir = deps_dir
        self.max_tiles = max_tiles
        # repetition_penalty 1.05: tắt hẳn thì model kẹt vòng lặp, quá mạnh thì hại số tiền lặp lại
        self.gen_cfg = {"max_new_tokens": max_new_tokens, "do_sample": False, "num_beams": 1,
                        "repetition_penalty": 1.05}
        self._lock = threading.Lock()
        self._ready = False

    def _load(self) -> None:
        _use_ocr_deps(self.deps_dir)
        try:
            import torch
            import torchvision.transforms as T
            from torchvision.transforms.functional import InterpolationMode
            from transformers import AutoModel, AutoTokenizer
        except ImportError as e:
            raise OcrUnavailableError(f"Thiếu gói OCR ({e.name}); cài requirements-ocr.txt") from e
        try:
            use_cuda = torch.cuda.is_available()
            self.torch = torch
            self.dtype = torch.bfloat16 if use_cuda else torch.float32
            self.device = "cuda" if use_cuda else "cpu"
            self.model = AutoModel.from_pretrained(
                self.model_id, torch_dtype=self.dtype, low_cpu_mem_usage=True,
                trust_remote_code=True, use_flash_attn=False).eval().to(self.device)
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_id, trust_remote_code=True, use_fast=False)
        except Exception as e:  # noqa: BLE001
            raise OcrUnavailableError(f"Không nạp được model {self.model_id}: {str(e)[:200]}") from e
        self.transform = T.Compose([
            T.Lambda(lambda im: im.convert("RGB")),
            T.Resize((TILE, TILE), interpolation=InterpolationMode.BICUBIC),
            T.ToTensor(),
            T.Normalize(mean=_MEAN, std=_STD),
        ])
        self._ready = True
        logger.info("[OCR] Đã nạp %s trên %s", self.model_id, self.device)

    def _tiles(self, image):
        """Chia ảnh thành các ô 448x448 theo tỉ lệ gần nhất (chuẩn InternVL), kèm ảnh thu nhỏ toàn cảnh."""
        w, h = image.size
        ratios = sorted({(i, j) for n in range(1, self.max_tiles + 1)
                         for i in range(1, n + 1) for j in range(1, n + 1)
                         if 1 <= i * j <= self.max_tiles}, key=lambda x: x[0] * x[1])
        aspect = w / h
        best, best_diff = (1, 1), float("inf")
        for r in ratios:
            diff = abs(aspect - r[0] / r[1])
            if diff < best_diff or (diff == best_diff and w * h > 0.5 * TILE * TILE * r[0] * r[1]):
                best, best_diff = r, diff
        resized = image.resize((TILE * best[0], TILE * best[1]))
        tiles = []
        for i in range(best[0] * best[1]):
            col, row = i % best[0], i // best[0]
            tiles.append(resized.crop((col * TILE, row * TILE, (col + 1) * TILE, (row + 1) * TILE)))
        if len(tiles) > 1:
            tiles.append(image.resize((TILE, TILE)))
        return tiles

    def extract_text(self, image) -> Dict:
        """Ảnh PIL -> {"text", "latency_ms", "n_tiles"}. Gọi đồng bộ, chạy trong thread."""
        with self._lock:
            if not self._ready:
                self._load()
            start = time.perf_counter()
            tiles = self._tiles(image)
            pixel_values = self.torch.stack([self.transform(t) for t in tiles]).to(self.dtype).to(self.device)
            with self.torch.no_grad():
                text = self.model.chat(self.tokenizer, pixel_values, OCR_PROMPT, self.gen_cfg)
        return {"text": collapse_repeats(text), "n_tiles": len(tiles),
                "latency_ms": round((time.perf_counter() - start) * 1000, 1)}


_vintern = None
_gemini = None
_engine_lock = threading.Lock()


def _get_vintern() -> VinternEngine:
    global _vintern
    from app.configs.settings import settings
    with _engine_lock:
        if _vintern is None:
            _vintern = VinternEngine(settings.OCR_MODEL_ID, max_tiles=settings.OCR_MAX_TILES,
                                     deps_dir=settings.OCR_DEPS_DIR)
        return _vintern


def _get_gemini():
    global _gemini
    from app.configs.settings import settings
    from app.ai.ocr.gemini_engine import GeminiOcrEngine
    with _engine_lock:
        if _gemini is None:
            _gemini = GeminiOcrEngine(settings.OCR_GEMINI_MODEL)
        return _gemini


def _has_gpu() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except ImportError:
        return False


def resolve_engine_name() -> str:
    """
    OCR_ENGINE: vintern | gemini | auto (mặc định).
    auto: có GPU -> Vintern (vài giây/ảnh); chỉ có CPU -> Gemini, vì Vintern trên CPU mất 4-5 phút/hóa đơn thật.
    """
    from app.configs.settings import settings
    choice = (settings.OCR_ENGINE or "auto").lower()
    if choice in ("vintern", "gemini"):
        return choice
    return "vintern" if _has_gpu() else "gemini"


def extract_text(image) -> Dict:
    """Ảnh -> {"text", "n_tiles", "latency_ms", "engine"}. Vintern lỗi thì chuyển sang Gemini (nếu có khóa)."""
    from app.configs.settings import settings
    name = resolve_engine_name()
    if name == "vintern":
        try:
            return {**_get_vintern().extract_text(image), "engine": "vintern"}
        except OcrUnavailableError as e:
            if not (settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")):
                raise
            logger.warning("[OCR] Vintern không dùng được (%s), chuyển sang Gemini", e)
    return {**_get_gemini().extract_text(image), "engine": "gemini"}
