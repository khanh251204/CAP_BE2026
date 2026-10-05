import json
import re
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

import os 

# Giả định import Session DB từ core project của bạn
# from core.database import get_db

# ==============================================================================
# 1. SCHEMAS (DATA CONTRACTS)
# ==============================================================================

class EntitySchema(BaseModel):
    product: Optional[str] = None
    price: Optional[float] = None
    quantity: Optional[float] = 1.0
    unit: Optional[str] = None
    customer: Optional[str] = None
    supplier: Optional[str] = None
    date: Optional[str] = None
    payment: Optional[str] = None

class TransactionAnalysis(BaseModel):
    status: str  # "success", "needs_confirmation", "cancelled", "failed"
    text: str
    intent: Optional[str] = None
    type: Optional[str] = None
    entities: EntitySchema
    missing_fields: List[str] = []
    message: Optional[str] = None
    requires_action: Optional[Dict[str, Any]] = None

class VoiceProcessRequest(BaseModel):
    text: str
    user_confirmation: Optional[bool] = None
    pending_data: Optional[Dict[str, Any]] = None


# ==============================================================================
# 2. PROMPT & GROQ SERVICE
# ==============================================================================

EXTRACTION_PROMPT = """
Bạn là trợ lý AI phân tích sổ thu chi cho tiểu thương Việt Nam.
Nhiệm vụ: Trích xuất thông tin từ câu nói sang JSON chuẩn xác.

Quy tắc chuyển đổi giá tiền:
- "30k", "30 ngàn", "30 nghìn" -> 30000
- "1 trăm" -> 100000
- "1 triệu", "1 củ" -> 1000000

Cấu trúc JSON đầu ra bắt buộc:
{
    "intent": "nhập_hàng" | "bán_hàng" | "chi_tiêu",
    "type": "expense" | "income",
    "entities": {
        "product": "Tên sản phẩm (chỉ viết hoa chữ cái đầu)",
        "price": số_tiền_chuyển_thành_mệnh_giá_vnd_integer,
        "quantity": số_lượng_float_hoặc_int,
        "unit": "đơn vị tính (trái, kg, cái...)",
        "customer": null,
        "supplier": null,
        "date": null,
        "payment": null
    }
}
Chỉ trả về JSON thuần, không viết thêm bất kỳ lời giải thích hay markdown codeblock nào khác.
"""
api_key = os.getenv("GROQ_API_KEY")
class GroqService:
    def __init__(self, api_key: str = api_key):
        # Import groqclient ở đây hoặc dùng httpx/requests trực tiếp
        # from groq import Groq
        # self.client = Groq(api_key=api_key)
        pass

    async def parse_text(self, text: str) -> dict:
        """Gọi Groq API và parse JSON trả về"""
        # --- BẮT ĐẦU MOCK/IMPLEMENTATION CỦA GROQ ---
        # Code thực tế sẽ gọi:
        # response = self.client.chat.completions.create(
        #     model="llama-3.3-70b-versatile",
        #     messages=[
        #         {"role": "system", "content": EXTRACTION_PROMPT},
        #         {"role": "user", "content": text}
        #     ],
        #     temperature=0.1
        # )
        # raw_json = response.choices[0].message.content
        
        # Giả lập kết quả Groq trả về cho câu "Nhập 3 trái cà chua 30k":
        return {
            "intent": "nhập_hàng",
            "type": "expense",
            "entities": {
                "product": "Cà chua",
                "price": 30000,
                "quantity": 3,
                "unit": "trái",
                "customer": None,
                "supplier": None,
                "date": None,
                "payment": None
            }
        }


# ==============================================================================
# 3. AGENT SERVICE (CORE LOGIC & DB INTERACTION)
# ==============================================================================

class VoiceAgentService:
    def __init__(self, db: Session):
        self.db = db
        self.llm = GroqService()

    def _check_product_exists(self, product_name: str) -> bool:
        """Kiểm tra sản phẩm trong database"""
        # Thay 'products' và 'name' bằng bảng/cột thực tế trong DB của bạn
        # query = text("SELECT id FROM products WHERE LOWER(name) = LOWER(:name)")
        # result = self.db.execute(query, {"name": product_name}).fetchone()
        # return result is not None
        
        # Giả lập: Trả về False để test luồng hỏi xác nhận thêm mới
        return False

    def _create_product(self, product_name: str, unit: Optional[str]):
        """Thêm mới sản phẩm vào database"""
        # query = text("INSERT INTO products (name, unit) VALUES (:name, :unit)")
        # self.db.execute(query, {"name": product_name, "unit": unit})
        # self.db.commit()
        pass

    def _create_transaction(self, data: dict):
        """Tạo bản ghi giao dịch thu/chi"""
        # Logic chèn giao dịch vào DB
        pass

    async def execute(
        self, 
        text_input: str, 
        user_confirmation: Optional[bool] = None, 
        pending_data: Optional[dict] = None
    ) -> TransactionAnalysis:
        
        # ----------------------------------------------------------------------
        # LUỒNG 1: Xử lý khi nhận phản hồi Đồng ý/Từ chối từ FE (User Confirmation)
        # ----------------------------------------------------------------------
        if user_confirmation is not None and pending_data:
            entities = pending_data.get("entities", {})
            
            if user_confirmation:
                # 1. Thêm sản phẩm mới vào DB
                self._create_product(
                    product_name=entities.get("product"), 
                    unit=entities.get("unit")
                )
                # 2. Tạo giao dịch nhập hàng
                self._create_transaction(pending_data)

                return TransactionAnalysis(
                    status="success",
                    text=text_input,
                    intent=pending_data.get("intent"),
                    type=pending_data.get("type"),
                    entities=EntitySchema(**entities),
                    message=f"Đã thêm mới '{entities.get('product')}' vào danh mục và ghi nhận giao dịch thành công."
                )
            else:
                return TransactionAnalysis(
                    status="cancelled",
                    text=text_input,
                    intent=pending_data.get("intent"),
                    type=pending_data.get("type"),
                    entities=EntitySchema(**entities),
                    message="Đã hủy thao tác ghi nhận giao dịch."
                )

        # ----------------------------------------------------------------------
        # LUỒNG 2: Xử lý câu nói mới từ người dùng
        # ----------------------------------------------------------------------
        extracted_data = await self.llm.parse_text(text_input)
        entities_dict = extracted_data.get("entities", {})
        product_name = entities_dict.get("product")

        if not product_name:
            return TransactionAnalysis(
                status="failed",
                text=text_input,
                intent=extracted_data.get("intent"),
                type=extracted_data.get("type"),
                entities=EntitySchema(**entities_dict),
                missing_fields=["product"],
                message="Không nhận diện được tên sản phẩm."
            )

        # Kiểm tra sản phẩm trong Database
        exists = self._check_product_exists(product_name)

        if not exists:
            # Nếu sản phẩm CHƯA CÓ -> Trả về câu hỏi xác nhận
            return TransactionAnalysis(
                status="needs_confirmation",
                text=text_input,
                intent=extracted_data.get("intent"),
                type=extracted_data.get("type"),
                entities=EntitySchema(**entities_dict),
                message=f"Sản phẩm '{product_name}' chưa có trong hệ thống. Bạn có muốn thêm mới không?",
                requires_action={
                    "action": "CREATE_PRODUCT_AND_TRANSACTION",
                    "payload": extracted_data
                }
            )

        # Nếu sản phẩm ĐÃ CÓ -> Ghi trực tiếp giao dịch
        self._create_transaction(extracted_data)
        
        return TransactionAnalysis(
            status="success",
            text=text_input,
            intent=extracted_data.get("intent"),
            type=extracted_data.get("type"),
            entities=EntitySchema(**entities_dict),
            message="Ghi nhận giao dịch thành công."
        )


# ==============================================================================
# 4. FASTAPI ROUTER
# ==============================================================================

router = APIRouter(prefix="/agent", tags=["Voice Agent"])

@router.post("/process-voice", response_model=TransactionAnalysis)
async def process_voice(
    payload: VoiceProcessRequest, 
    # db: Session = Depends(get_db) # Bật khi kết nối DB thật
):
    # Fake session db để chạy thử
    db = None 
    
    agent = VoiceAgentService(db=db)
    result = await agent.execute(
        text_input=payload.text,
        user_confirmation=payload.user_confirmation,
        pending_data=payload.pending_data
    )
    return result