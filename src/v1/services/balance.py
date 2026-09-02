from prisma import Prisma
from chauff_cmn.models import User

from ..errors import CurrencyNotFoundError


async def get_balance_by_id(db: Prisma, user_id: int, currency_name: str) -> int:
    currency = await db.currency.find_unique(where={"name": currency_name})
    if not currency:
        raise CurrencyNotFoundError()
    wallet = await db.wallet.find_unique(where={
        "currencyId_userId": {
            "currencyId": currency.id,
            "userId": user_id
        }
    })
    if not wallet:
        return 0
    return wallet.balance

async def get_balance(db: Prisma, user: User, currency_name: str) -> int:
    return await get_balance_by_id(db, int(user.user_id), currency_name)