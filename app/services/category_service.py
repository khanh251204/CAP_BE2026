from app.repositories.category_repository import CategoryRepository


class CategoryService:

    @staticmethod
    def get_all_categories():
        return CategoryRepository.get_all()
