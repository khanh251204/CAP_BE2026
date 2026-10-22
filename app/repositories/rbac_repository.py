from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.role_permission_model import Role, Permission
from app.models.user_model import User


class RBACRepository:

    @staticmethod
    def get_all_roles(db: Session) -> List[Role]:
        return db.query(Role).order_by(Role.role_id.asc()).all()

    @staticmethod
    def get_role_by_id(db: Session, role_id: int) -> Optional[Role]:
        return db.query(Role).filter(Role.role_id == role_id).first()

    @staticmethod
    def get_role_by_name(db: Session, role_name: str) -> Optional[Role]:
        return db.query(Role).filter(Role.role_name.ilike(role_name.strip())).first()

    @staticmethod
    def count_users_by_role_id(db: Session, role_id: int) -> int:
        return db.query(func.count(User.user_id)).filter(User.role_id == role_id).scalar() or 0

    @staticmethod
    def get_all_permissions(db: Session) -> List[Permission]:
        return db.query(Permission).order_by(Permission.module.asc(), Permission.permission_id.asc()).all()

    @staticmethod
    def get_permissions_by_ids(db: Session, ids: List[int]) -> List[Permission]:
        if not ids:
            return []
        return db.query(Permission).filter(Permission.permission_id.in_(ids)).all()

    @staticmethod
    def create_role(db: Session, role_name: str, description: Optional[str] = None, permissions: Optional[List[Permission]] = None) -> Role:
        new_role = Role(
            role_name=role_name.strip().upper(),
            description=description,
            is_system=False
        )
        if permissions:
            new_role.permissions = permissions
        db.add(new_role)
        db.commit()
        db.refresh(new_role)
        return new_role

    @staticmethod
    def update_role(db: Session, role: Role, role_name: Optional[str] = None, description: Optional[str] = None, permissions: Optional[List[Permission]] = None) -> Role:
        if role_name:
            role.role_name = role_name.strip().upper()
        if description is not None:
            role.description = description
        if permissions is not None:
            role.permissions = permissions
        db.commit()
        db.refresh(role)
        return role

    @staticmethod
    def delete_role(db: Session, role: Role) -> None:
        db.delete(role)
        db.commit()

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        return db.query(User).filter(User.user_id == user_id).first()
