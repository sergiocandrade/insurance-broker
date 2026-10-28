from datetime import datetime

from pydantic import BaseModel, ConfigDict

from domain.models.broker import BrokerStatus


class BrokerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: BrokerStatus
    created_at: datetime