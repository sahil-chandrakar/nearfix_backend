from fastapi import APIRouter

from app.api.deps import DBSession
from app.schemas.category import ServiceCategoryRead
from app.services.category_service import CategoryService

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[ServiceCategoryRead])
def list_categories(db: DBSession) -> list[ServiceCategoryRead]:
    return CategoryService.list_categories(db)
