from authentication_types.models import User
from prisma import Prisma
from prisma.models import Claim, Currency
from datetime import datetime, timezone

from ..services.transaction import add_to_wallet


def _compute_claimable(now: datetime, last_claim: Claim | None, currency: Currency) -> int:
    if not last_claim:
        return currency.claimLimit
    return int(
        min(
            (now - last_claim.lastClaimAt).total_seconds() * currency.claimRate,
            currency.claimLimit,
        )
    )

async def get_last_claim(db: Prisma, user: User, currency: Currency):
    return await db.claim.find_unique(
        where={
            "currencyId_userId": {
                "currencyId": currency.id,
                "userId": int(user.user_id),
            }
        }
    )

async def get_currency_by_name(db: Prisma, currency_name: str) -> Currency:
    currency = await db.currency.find_unique(where={"name": currency_name})
    if not currency:
        raise ValueError("Currency not found")
    return currency


async def get_claimable_for_currency(db: Prisma, user: User, currency: Currency) -> int:
    now = datetime.now(timezone.utc)
    last_claim = await get_last_claim(db, user, currency)
    return _compute_claimable(now, last_claim, currency)


async def get_claimable(db: Prisma, user: User, currency_name: str) -> int:
    currency = await get_currency_by_name(db, currency_name)
    return await get_claimable_for_currency(db, user, currency)

async def claim(db: Prisma, user: User, currency_name: str):
    currency = await get_currency_by_name(db, currency_name)
    claimable = await get_claimable_for_currency(db, user, currency)

    async with db.tx() as tx:
        await tx.claim.update(
            where={
                "currencyId_userId": {
                    "currencyId": currency.id,
                    "userId": int(user.user_id),
                }
            },
            data={"lastClaimAt": datetime.now(timezone.utc)},
        )
        await add_to_wallet(tx, user, claimable, currency)
    return claimable
