from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class OrganizationContext:
    """Internal context: a future auth adapter must verify membership before constructing it.

    Never construct this from an unverified organization header or request parameter.
    UUID scoping and composite foreign keys do not replace authorization.
    """

    organization_id: UUID
    user_id: UUID
