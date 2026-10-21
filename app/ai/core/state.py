# app/ai/core/state.py
"""
Distributed confirmation state management.
Replaces in-memory dictionary with SessionStoreService proxy to ensure
multi-worker and multi-container resilience without losing pending sessions.
"""
from app.services.session_store_service import PendingConfirmationsProxy

# Distributed proxy behaves like a dict but stores in Redis/DB with 600s TTL
pending_confirmations = PendingConfirmationsProxy()
