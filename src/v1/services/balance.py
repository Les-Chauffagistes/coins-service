from prisma import Prisma
from authentication_types.models import User


async def get_balance(db: Prisma, user: User, currency_name: str) -> int:
    currency = await db.currency.find_unique(where={"name": currency_name})
    if not currency:
        raise ValueError("Currecy not found")
    wallet = await db.wallet.find_unique(where={
        "currencyId_userId": {
            "currencyId": currency.id,
            "userId": int(user.user_id)
        }
    })
    if not wallet:
        return 0
    return wallet.balance