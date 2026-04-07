from prisma.models import Currency
from authentication_types.models import User
from prisma import Prisma


async def add_record(tx: Prisma, user: User, source: str, destination: str, reason: str, amount: int, currency: Currency):
    return await tx.log.create({
        "amount": amount,
        "currencyId": currency.id,
        "fromState": source,
        "toState": destination,
        "reason": reason,
        "userId": int(user.user_id),
    })