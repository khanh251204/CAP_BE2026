from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.repositories.rbac_repository import RBACRepository
from app.services.permission_service import PermissionService, UserAccess
from app.schemas.rbac_schema import (
    RoleItem,
    RoleListResponse,
    PermissionItem,
    PermissionGroupItem,
    RoleCreateRequest,
    RoleUpdateRequest
)


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _check_can_grant(actor: Optional[UserAccess], codes) -> None:
    """Chống leo thang đặc quyền: người không phải ADMIN chỉ được cấp các quyền chính mình đang có."""
    if actor is None or actor.is_admin:
        return
    missing = sorted(set(codes) - set(actor.permissions))
    if missing:
        raise _forbidden(f"Bạn không thể cấp các quyền mà bạn không có: {', '.join(missing)}")


class RBACService:

    @staticmethod
    def _actor(db: Session, actor_id: Optional[int]) -> Optional[UserAccess]:
        return PermissionService.get_user_access(actor_id, db) if actor_id else None

    @staticmethod
    def get_roles_with_counts(db: Session) -> RoleListResponse:
        roles = RBACRepository.get_all_roles(db)
        items = []
        for r in roles:
            count = RBACRepository.count_users_by_role_id(db, r.role_id)
            items.append(RoleItem(
                role_id=r.role_id,
                role_name=r.role_name,
                description=r.description,
                is_system=r.is_system,
                user_count=count,
                permissions=[PermissionItem.model_validate(p) for p in r.permissions],
                created_at=r.created_at
            ))
        return RoleListResponse(items=items, total=len(items))

    @staticmethod
    def get_role_detail(db: Session, role_id: int) -> RoleItem:
        role = RBACRepository.get_role_by_id(db, role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy vai trò")
        count = RBACRepository.count_users_by_role_id(db, role.role_id)
        return RoleItem(
            role_id=role.role_id,
            role_name=role.role_name,
            description=role.description,
            is_system=role.is_system,
            user_count=count,
            permissions=[PermissionItem.model_validate(p) for p in role.permissions],
            created_at=role.created_at
        )

    @staticmethod
    def get_permissions_grouped(db: Session) -> List[PermissionGroupItem]:
        perms = RBACRepository.get_all_permissions(db)
        groups: Dict[str, List[PermissionItem]] = {}
        for p in perms:
            groups.setdefault(p.module, []).append(PermissionItem.model_validate(p))
        return [PermissionGroupItem(module=m, permissions=p_list) for m, p_list in groups.items()]

    @staticmethod
    def create_role(db: Session, req: RoleCreateRequest, actor_id: Optional[int] = None) -> RoleItem:
        norm_name = req.role_name.strip().upper()
        if RBACRepository.get_role_by_name(db, norm_name):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Vai trò '{norm_name}' đã tồn tại")

        perms = []
        if req.permission_ids:
            perms = RBACRepository.get_permissions_by_ids(db, req.permission_ids)
        _check_can_grant(RBACService._actor(db, actor_id), [p.code for p in perms])

        new_role = RBACRepository.create_role(db, role_name=norm_name, description=req.description, permissions=perms)
        return RoleItem(
            role_id=new_role.role_id,
            role_name=new_role.role_name,
            description=new_role.description,
            is_system=new_role.is_system,
            user_count=0,
            permissions=[PermissionItem.model_validate(p) for p in new_role.permissions],
            created_at=new_role.created_at
        )

    @staticmethod
    def update_role(db: Session, role_id: int, req: RoleUpdateRequest, actor_id: Optional[int] = None) -> RoleItem:
        role = RBACRepository.get_role_by_id(db, role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy vai trò")

        actor = RBACService._actor(db, actor_id)
        if actor and not actor.is_admin:
            if role.role_name.upper() == "ADMIN":
                raise _forbidden("Chỉ ADMIN mới được chỉnh vai trò ADMIN")
            if actor.role_name == role.role_name.upper():
                raise _forbidden("Bạn không thể tự chỉnh quyền của vai trò mình đang giữ")

        if req.role_name and req.role_name.strip().upper() != role.role_name:
            if role.is_system:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Không được đổi tên vai trò hệ thống mặc định")
            norm_name = req.role_name.strip().upper()
            exist = RBACRepository.get_role_by_name(db, norm_name)
            if exist and exist.role_id != role_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Vai trò '{norm_name}' đã tồn tại")

        perms = None
        if req.permission_ids is not None:
            perms = RBACRepository.get_permissions_by_ids(db, req.permission_ids)
            current_codes = {p.code for p in role.permissions}
            # Chỉ kiểm tra quyền được THÊM; bỏ bớt quyền thì luôn được phép
            _check_can_grant(actor, [p.code for p in perms if p.code not in current_codes])

        updated = RBACRepository.update_role(
            db=db,
            role=role,
            role_name=req.role_name,
            description=req.description,
            permissions=perms
        )
        PermissionService.clear_cache()
        count = RBACRepository.count_users_by_role_id(db, updated.role_id)
        return RoleItem(
            role_id=updated.role_id,
            role_name=updated.role_name,
            description=updated.description,
            is_system=updated.is_system,
            user_count=count,
            permissions=[PermissionItem.model_validate(p) for p in updated.permissions],
            created_at=updated.created_at
        )

    @staticmethod
    def delete_role(db: Session, role_id: int, actor_id: Optional[int] = None) -> None:
        role = RBACRepository.get_role_by_id(db, role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy vai trò")
        _check_can_grant(RBACService._actor(db, actor_id), [p.code for p in role.permissions])
        if role.is_system:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Không thể xóa vai trò hệ thống mặc định")
        
        user_count = RBACRepository.count_users_by_role_id(db, role_id)
        if user_count > 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Vai trò này đang có {user_count} người dùng, hãy chuyển người dùng sang vai trò khác trước khi xóa")

        RBACRepository.delete_role(db, role)
        PermissionService.clear_cache()

    @staticmethod
    def assign_user_role(db: Session, user_id: int, role_id: int, actor_id: Optional[int] = None) -> Dict[str, Any]:
        user = RBACRepository.get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng")
        role = RBACRepository.get_role_by_id(db, role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy vai trò cần gán")

        if actor_id is not None and actor_id == user_id:
            raise _forbidden("Bạn không thể tự thay đổi vai trò của chính mình")

        actor = RBACService._actor(db, actor_id)
        target_is_admin = (user.role or "").upper() == "ADMIN"
        new_is_admin = role.role_name.upper() == "ADMIN"
        if actor and not actor.is_admin:
            if new_is_admin or target_is_admin:
                raise _forbidden("Chỉ ADMIN mới được gán hoặc thu hồi vai trò ADMIN")
            _check_can_grant(actor, [p.code for p in role.permissions])

        if target_is_admin and not new_is_admin:
            admin_count = RBACRepository.count_users_by_role_id(db, user.role_id)
            if admin_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Không thể hạ quyền ADMIN cuối cùng của hệ thống"
                )

        user.role_id = role.role_id
        db.commit()
        db.refresh(user)
        PermissionService.clear_cache(user.user_id)

        return {
            "success": True,
            "message": f"Đã gán vai trò '{role.role_name}' cho người dùng {user.full_name}",
            "user_id": user.user_id,
            "role_id": user.role_id,
            "role": user.role
        }
