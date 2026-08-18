from pydantic import BaseModel, PositiveInt


class CreditPayload(BaseModel):
    amount: PositiveInt
    currency: str
    source: str
    reason: str
    idempotencyKey: str

class BurnPayload(BaseModel):
    amount: PositiveInt
    currency: str
    destination: str
    reason: str
    idempotencyKey: str

class TransferPayload(BaseModel):
    amount: PositiveInt
    currency: str
    fromUserId: int
    toUserId: int
    reason: str
    idempotencyKey: str