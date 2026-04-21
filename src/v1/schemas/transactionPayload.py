from pydantic import BaseModel


class CreditPayload(BaseModel):
    amount: int
    currency: str
    source: str
    reason: str
    idempotencyKey: str

class BurnPayload(BaseModel):
    amount: int
    currency: str
    destination: str
    reason: str
    idempotencyKey: str