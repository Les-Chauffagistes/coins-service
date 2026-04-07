from authentication_types.models import User
from prisma import Prisma
from prisma.models import Currency
from ..services.log import add_record


async def add_to_wallet(tx: Prisma, user: User, amount: int, currency: Currency):
    wallet = await tx.wallet.find_unique(
        where={
            "currencyId_userId": {
                "currencyId": currency.id,
                "userId": int(user.user_id),
            }
        }
    )
    if not wallet:
        await tx.wallet.create(
            {"balance": int(amount), "currencyId": currency.id, "userId": int(user.user_id)}
        )
        return
    await tx.wallet.update(
        where={
            "currencyId_userId": {
                "currencyId": currency.id,
                "userId": int(user.user_id)
            }
        },
        data={
            "balance": wallet.balance + amount
        }
    )

async def remove_from_wallet(tx: Prisma, user: User, amount: int, currency: Currency):
    wallet = await tx.wallet.find_unique(
        where={
            "currencyId_userId": {
                "currencyId": currency.id,
                "userId": int(user.user_id),
            }
        }
    )
    if not wallet:
        raise ValueError("Wallet not found")
    
    await tx.wallet.update(
        where={
            "currencyId_userId": {
                "currencyId": currency.id,
                "userId": int(user.user_id)
            }
        },
        data={
            "balance": wallet.balance - amount
        }
    )


async def credit_wallet(tx: Prisma, user: User, amount: int, currency_name: str, source: str, reason: str):
    currency = await tx.currency.find_unique(where={"name": currency_name})
    if not currency:
        raise ValueError("Currency not found")
    
    await add_record(tx, user, source, "wallet", reason, amount, currency)
    return await add_to_wallet(tx, user, amount, currency)

async def burn_wallet(tx: Prisma, user: User, amount: int, currency_name: str, destination: str, reason: str):
    currency = await tx.currency.find_unique(where={"name": currency_name})
    if not currency:
        raise ValueError("Currency not found")
    
    await add_record(tx, user, "wallet", destination, reason, amount, currency)
    return await remove_from_wallet(tx, user, amount, currency)