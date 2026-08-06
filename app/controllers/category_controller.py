from sqlalchemy.orm import Session
from app.services.category_service import CategoryService


class CategoryController:

    @staticmethod
    def get_all_categories(db: Session):
        data = CategoryService.get_all_categories(db)

        return {
            "success": True,
            "data": data
        }