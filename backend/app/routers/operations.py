"""User-facing action ledger endpoints."""
from fastapi import APIRouter, Depends, Query

from ..operation_ledger import recent_operations
from .squads import get_current_user_id


router = APIRouter(prefix="/api/operations", tags=["operations"])


@router.get("/recent")
async def list_recent_operations(
    limit: int = Query(default=30, ge=1, le=100),
    user_id: int = Depends(get_current_user_id),
):
    """Return the authenticated manager's durable action receipts."""
    return {"operations": recent_operations(user_id, limit=limit)}
