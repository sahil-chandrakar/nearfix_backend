from mimetypes import guess_type
from pathlib import Path, PurePosixPath
from shutil import copyfileobj
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response

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
    def _storage_backend() -> str:
        return settings.storage_backend

    @staticmethod
    def _clean_relative_key(path: str) -> str:
        normalized = str(PurePosixPath(path.replace("\\", "/"))).lstrip("/")
        prefixes = [settings.upload_dir, settings.gcs_upload_prefix]
        for prefix in prefixes:
            clean_prefix = str(PurePosixPath(prefix.replace("\\", "/"))).strip("/")
            if clean_prefix and normalized.startswith(f"{clean_prefix}/"):
                normalized = normalized[len(clean_prefix) + 1 :]

        parts = PurePosixPath(normalized).parts
        if not normalized or normalized == "." or any(part == ".." for part in parts):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found",
            )
        return normalized

    @staticmethod
    def _local_path(path: str) -> Path:
        upload_root = Path(settings.upload_dir).resolve()
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = Path(settings.upload_dir) / UploadService._clean_relative_key(path)
        candidate = candidate.resolve()
        if not candidate.is_relative_to(upload_root):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found",
            )
        return candidate

    @staticmethod
    def _gcs_object_name(path: str) -> str:
        key = UploadService._clean_relative_key(path)
        prefix = settings.gcs_upload_prefix.strip("/")
        return f"{prefix}/{key}" if prefix else key

    @staticmethod
    def _gcs_bucket():
        if not settings.gcs_bucket_name:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="GCS bucket is not configured",
            )
        from google.cloud import storage

        return storage.Client().bucket(settings.gcs_bucket_name)

    @staticmethod
    def _save_upload(*, file: UploadFile, key: str, content_type: str) -> str:
        if UploadService._storage_backend() == "gcs":
            blob = UploadService._gcs_bucket().blob(UploadService._gcs_object_name(key))
            file.file.seek(0)
            blob.upload_from_file(file.file, content_type=content_type)
            return key

        target_path = UploadService._local_path(key)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        file.file.seek(0)
        with target_path.open("wb") as output_file:
            copyfileobj(file.file, output_file)

        return key

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

        key = f"providers/{phone}/{document_name}-{uuid4().hex}{extension}"
        return UploadService._save_upload(
            file=file,
            key=key,
            content_type=file.content_type or "image/jpeg",
        )

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

        key = f"banners/customer-banner-{uuid4().hex}{extension}"
        return UploadService._save_upload(
            file=file,
            key=key,
            content_type=file.content_type or "application/octet-stream",
        )

    @staticmethod
    def resolve_safe_upload_path(path: str) -> Path:
        candidate = UploadService._local_path(path)
        if not candidate.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found",
            )
        return candidate

    @staticmethod
    def file_response(path: str) -> Response:
        if UploadService._storage_backend() == "gcs":
            object_name = UploadService._gcs_object_name(path)
            blob = UploadService._gcs_bucket().get_blob(object_name)
            if blob is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="File not found",
                )
            return Response(
                content=blob.download_as_bytes(),
                media_type=blob.content_type or guess_type(object_name)[0] or "application/octet-stream",
            )

        return FileResponse(UploadService.resolve_safe_upload_path(path))

    @staticmethod
    def delete_file(path: str) -> None:
        if UploadService._storage_backend() == "gcs":
            blob = UploadService._gcs_bucket().get_blob(UploadService._gcs_object_name(path))
            if blob is not None:
                blob.delete()
            return

        try:
            UploadService.resolve_safe_upload_path(path).unlink()
        except HTTPException:
            return
