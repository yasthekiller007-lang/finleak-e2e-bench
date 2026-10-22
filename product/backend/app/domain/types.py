from enum import StrEnum


class DocumentType(StrEnum):
    CONTRACT = "contract"
    INVOICE = "invoice"
    PURCHASE_ORDER = "purchase_order"
    CREDIT_NOTE = "credit_note"
    OTHER = "other"


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"
    NEEDS_OCR = "needs_ocr"


class MembershipRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class VersionKind(StrEnum):
    ORIGINAL = "original"
    AMENDMENT = "amendment"


class CaseStatus(StrEnum):
    DETECTED = "detected"
    NEEDS_REVIEW = "needs_review"
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"


class Priority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"
