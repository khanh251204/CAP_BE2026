from sqlalchemy.orm import Session
from app.models.category_model import Category


class CategoryRepository:

    @staticmethod
    def get_all(db: Session):
        return db.query(Category).all()
