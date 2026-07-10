"""Document upload, storage, and metadata/versioning (spec §16.3, §20.2, §22).

Files are written under `settings.documents_dir/<project_id>/` only — never outside the
project data directory (§20.2 filesystem restriction).
"""
from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.document import DocumentRecord
from app.schemas.document import SUPPORTED_EXTENSIONS


class UnsupportedFormatError(ValueError):
    """Raised when an uploaded document's extension isn't PDF/DOCX/TXT/Markdown."""


def generate_document_id() -> str:
    return f"doc_{uuid.uuid4().hex[:12]}"


def _project_dir(settings: Settings, project_id: str) -> Path:
    project_dir = settings.documents_dir / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def _next_version(session: Session, project_id: str, document_name: str) -> str:
    count = session.scalar(
        select(func.count())
        .select_from(DocumentRecord)
        .where(
            DocumentRecord.project_id == project_id,
            DocumentRecord.document_name == document_name,
        )
    )
    return f"{(count or 0) + 1}.0"


def save_uploaded_document(
    session: Session,
    settings: Settings,
    project_id: str,
    filename: str,
    content: bytes,
    document_type: str = "",
) -> DocumentRecord:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFormatError(
            f"Unsupported document format '{extension}'. "
            f"Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    document_id = generate_document_id()
    dest = _project_dir(settings, project_id) / f"{document_id}{extension}"
    dest.write_bytes(content)

    document = DocumentRecord(
        document_id=document_id,
        project_id=project_id,
        document_name=filename,
        document_type=document_type,
        source_type="project",
        file_path=str(dest),
        document_version=_next_version(session, project_id, filename),
    )
    session.add(document)
    session.commit()
    session.refresh(document)
    return document


def save_text_document(
    session: Session,
    settings: Settings,
    project_id: str,
    document_name: str,
    text_content: str,
    document_type: str = "",
) -> DocumentRecord:
    filename = document_name if Path(document_name).suffix else f"{document_name}.txt"
    return save_uploaded_document(
        session,
        settings,
        project_id,
        filename,
        text_content.encode("utf-8"),
        document_type,
    )


def list_documents(session: Session, project_id: str) -> list[DocumentRecord]:
    return list(
        session.scalars(
            select(DocumentRecord).where(DocumentRecord.project_id == project_id)
        )
    )


def get_document(
    session: Session, project_id: str, document_id: str
) -> DocumentRecord | None:
    return session.scalar(
        select(DocumentRecord).where(
            DocumentRecord.project_id == project_id,
            DocumentRecord.document_id == document_id,
        )
    )


def delete_document(session: Session, project_id: str, document_id: str) -> bool:
    document = get_document(session, project_id, document_id)
    if document is None:
        return False
    file_path = Path(document.file_path)
    if file_path.exists():
        file_path.unlink()
    session.delete(document)
    session.commit()
    return True
