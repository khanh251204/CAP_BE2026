from typing import List, Optional

from pydantic import BaseModel, Field


class BomMaterialInput(BaseModel):
    material_product_id: int = Field(..., description="ID sản phẩm nguyên liệu (RAW_MATERIAL)")
    quantity_per_unit: float = Field(
        ..., gt=0,
        description="Lượng nguyên liệu cho 1 đơn vị thành phẩm (tối đa 2 chữ số thập phân sau khi đổi về đơn vị kho)",
    )
    unit: Optional[str] = Field(
        None,
        description="Đơn vị của quantity_per_unit (g, kg, gói...). Bỏ trống = đơn vị tính kho của nguyên liệu; "
                    "khác đơn vị kho thì tự quy đổi (bảng đo lường chung hoặc đơn vị quy đổi của nguyên liệu)",
    )


class BomReplaceRequest(BaseModel):
    """Ghi đè toàn bộ định mức của thành phẩm. Danh sách rỗng = xóa định mức."""
    materials: List[BomMaterialInput] = Field(default_factory=list)


class BomMaterialResponse(BaseModel):
    bom_id: int
    material_product_id: int
    material_name: str
    quantity_per_unit: float
    unit: Optional[str] = None
    material_is_active: bool


class BomResponse(BaseModel):
    finished_product_id: int
    product_name: str
    default_unit: Optional[str] = None
    materials: List[BomMaterialResponse]


class BomSummaryMaterial(BaseModel):
    material_product_id: int
    material_name: str
    quantity_per_unit: float
    unit: Optional[str] = None


class BomSummaryItem(BaseModel):
    """Một thành phẩm trong màn Công thức món: kèm định mức hiện có (rỗng = chưa khai báo)."""
    finished_product_id: int
    product_name: str
    default_unit: Optional[str] = None
    materials: List[BomSummaryMaterial]
