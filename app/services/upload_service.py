from pathlib import Path
from shutil import copyfileobj
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings


class UploadService:
    allowed_jpeg_content_types = {"image/jpeg", "image/jpg", "image/pjpeg"}
    allowed_jpeg_extensions = {".jpg", ".jpeg"}
    allowed_banner_content_types = {
        "image/jpeg",
        "image/jpg",
        "image/pjpeg",
        "image/png",
        "image/webp",
    }
    allowed_banner_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    max_banner_bytes = 5 * 1024 * 1024

    @staticmethod
    def save_provider_document(
        *,
        file: UploadFile,
        phone: str,
        document_name: str,
    ) -> str:
        if file.content_type not in UploadService.allowed_jpeg_content_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{document_name} must be a JPG image",
            )

        extension = Path(file.filename or "").suffix.lower()
        if extension not in UploadService.allowed_jpeg_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{document_name} must use a .jpg or .jpeg extension",
            )

        target_dir = Path(settings.upload_dir) / "providers" / phone
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{document_name}-{uuid4().hex}{extension}"

        file.file.seek(0)
        with target_path.open("wb") as output_file:
            copyfileobj(file.file, output_file)

        return target_path.as_posix()

    @staticmethod
    def save_banner_image(*, file: UploadFile) -> str:
        if file.content_type not in UploadService.allowed_banner_content_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Banner image must be JPG, PNG, or WebP",
            )

        extension = Path(file.filename or "").suffix.lower()
        if extension not in UploadService.allowed_banner_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Banner image must use .jpg, .jpeg, .png, or .webp",
            )

        file.file.seek(0, 2)
        size = file.file.tell()
        if size > UploadService.max_banner_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Banner image must be 5MB or smaller",
            )

        target_dir = Path(settings.upload_dir) / "banners"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"customer-banner-{uuid4().hex}{extension}"

        file.file.seek(0)
        with target_path.open("wb") as output_file:
            copyfileobj(file.file, output_file)

        return target_path.as_posix()

    @staticmethod
    def resolve_safe_upload_path(path: str) -> Path:
        upload_root = Path(settings.upload_dir).resolve()
        candidate = Path(path).resolve()
        if not candidate.is_relative_to(upload_root) or not candidate.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found",
            )
        return candidate
