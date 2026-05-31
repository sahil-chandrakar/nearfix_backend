from fastapi import APIRouter

from app.api.deps import DBSession
from app.repositories.support_repository import SupportRepository
from app.schemas.support import SupportDetailsRead

router = APIRouter(tags=["support"])


@router.get("/support-details", response_model=SupportDetailsRead)
def read_support_details(db: DBSession) -> SupportDetailsRead:
    return SupportRepository.get_details(db)
