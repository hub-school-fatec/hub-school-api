from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user_id


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
def get_authenticated_user(
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> dict[str, str]:
    return {"user_id": user_id}
