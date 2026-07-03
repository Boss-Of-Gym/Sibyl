from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class EventEnvelope[PayloadT: BaseModel](BaseModel):
    schema_version: int
    event_type: str
    occurred_at: datetime
    installation_id: UUID
    payload: PayloadT
