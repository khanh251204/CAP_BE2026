# app/repositories/debt_repository.py
# Facade repository combining query and command operations for Debt domain.

from app.repositories.debt.debt_query_repo import DebtQueryRepository
from app.repositories.debt.debt_command_repo import DebtCommandRepository


class DebtRepository(DebtQueryRepository, DebtCommandRepository):
    """
    Facade repository for Debt entities.
    Inherits all query methods from DebtQueryRepository
    and all command/mutation methods from DebtCommandRepository.
    100% backward compatible with existing calls.
    """
    pass


__all__ = ["DebtRepository"]