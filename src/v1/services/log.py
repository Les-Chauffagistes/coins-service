from prisma.models import Currency
from chauff_cmn.models import User
from prisma import Prisma


async def add_record_by_id(tx: Prisma, user_id: int, source: str, destination: str, reason: str, amount: int, currency: Currency):
    return await tx.log.create({
        "amount": amount,
        "currencyId": currency.id,
        "fromState": source,
        "toState": destination,
        "reason": reason,
        "userId": user_id,
    })

async def add_record(tx: Prisma, user: User, source: str, destination: str, reason: str, amount: int, currency: Currency):
    return await add_record_by_id(tx, int(user.user_id), source, destination, reason, amount, currency)