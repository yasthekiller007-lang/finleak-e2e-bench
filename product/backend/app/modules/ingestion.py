from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.tenancy import OrganizationContext
from app.domain.types import DocumentType, ProcessingStatus
from app.modules.storage import StoredObject


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    original_filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=127)
    file_size: int = Field(ge=0)
    storage_key: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    document_type: DocumentType
    processing_status: ProcessingStatus
    uploaded_at: datetime


class DocumentIngestion(Protocol):
    """Future orchestration must authorize first and compensate storage on DB failure."""

    def register(
        self,
        context: OrganizationContext,
        stored: StoredObject,
        original_filename: str,
        mime_type: str,
        document_type: DocumentType,
    ) -> DocumentMetadata: ...
