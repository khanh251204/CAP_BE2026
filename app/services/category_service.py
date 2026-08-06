from sqlalchemy.orm import Session
from app.repositories.category_repository import CategoryRepository


class CategoryService:

    @staticmethod
    def get_all_categories(db: Session):
        return CategoryRepository.get_all(db)