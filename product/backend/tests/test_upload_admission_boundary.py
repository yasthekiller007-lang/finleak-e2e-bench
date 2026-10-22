import asyncio

import pytest
from pydantic import ValidationError
from starlette.formparsers import MultiPartException

from app.api.documents import BODY_TIMEOUT_MESSAGE, UploadBodyLimit
from app.operations.intake_schema import IntakeLimits


def test_multipart_receipt_deadline_releases_work_instead_of_waiting_indefinitely():
    async def exercise():
        async def endpoint(scope, receive, send):
            await receive()

        async def stalled_receive():
            await asyncio.Event().wait()

        with pytest.raises(MultiPartException) as error:
            await UploadBodyLimit(endpoint, max_bytes=100, receipt_seconds=0.01)(
                {
                    "type": "http",
                    "method": "POST",
                    "headers": [(b"content-type", b"multipart/form-data; boundary=a")],
                },
                stalled_receive,
                None,
            )
        assert error.value.message == BODY_TIMEOUT_MESSAGE

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "changes",
    [
        {"upload_slots": 0},
        {"upload_slots": 5},
        {"process_slots": 5},
        {"actor_operations_per_minute": 0},
        {"actor_operations_per_minute": 1001},
        {"upload_slots": True},
        {"process_slots": "1"},
        {"profile": "unversioned"},
        {"unknown": 1},
    ],
)
def test_operational_profile_rejects_unbounded_or_ambiguous_values(changes):
    with pytest.raises(ValidationError):
        IntakeLimits(**changes)
