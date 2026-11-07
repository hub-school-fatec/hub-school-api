from typing import Annotated

from fastapi import Depends

from app.dependencies.auth import get_current_user_id
from app.repositories.base import Repository, get_repository
from app.services.academic import AcademicService


def get_service(
    user_id: Annotated[str, Depends(get_current_user_id)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> AcademicService:
    return AcademicService(repo, user_id)
