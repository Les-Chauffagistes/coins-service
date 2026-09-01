from chauff_cmn.models import User
from prisma import Prisma
from prisma.errors import UniqueViolationError
from prisma.models import Claim, Currency
from datetime import datetime, timezone

from ..errors import CurrencyNotFoundError
from ..services.transaction import add_to_wallet


SECONDS_PER_HOUR = 60 * 60


class ClaimConflictError(Exception):
    """Une autre réclamation concurrente a déjà mis à jour ce claim entre la lecture et l'écriture — l'appelant doit réessayer."""


def _compute_claimable(now: datetime, last_claim: Claim | None, currency: Currency) -> int:
    if not last_claim:
        return currency.claimLimit
    return int(
        min(
            (now - last_claim.lastClaimAt).total_seconds()
            * currency.claimRate
            / SECONDS_PER_HOUR,
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
        raise CurrencyNotFoundError()
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
    user_id = int(user.user_id)

    async with db.tx() as tx:
        last_claim = await get_last_claim(tx, user, currency)
        now = datetime.now(timezone.utc)
        claimable = _compute_claimable(now, last_claim, currency)

        if last_claim is None:
            # Premier claim pour ce couple (currency, user) : la contrainte
            # d'unicité (currencyId, userId) fait office de verrou si deux
            # requêtes concurrentes tentent toutes les deux la création.
            try:
                await tx.claim.create(
                    data={
                        "currencyId": currency.id,
                        "userId": user_id,
                        "lastClaimAt": now,
                    }
                )
            except UniqueViolationError:
                raise ClaimConflictError("concurrent claim, retry")
        else:
            # Update conditionné sur la valeur de lastClaimAt lue plus haut
            # (compare-and-swap) : si une requête concurrente a déjà claim
            # entre notre lecture et cet update, 0 ligne matche et on lève
            # une erreur plutôt que de créditer deux fois le même montant.
            updated = await tx.claim.update_many(
                where={
                    "currencyId": currency.id,
                    "userId": user_id,
                    "lastClaimAt": last_claim.lastClaimAt,
                },
                data={"lastClaimAt": now},
            )
            if updated == 0:
                raise ClaimConflictError("concurrent claim, retry")

        await add_to_wallet(tx, user, claimable, currency)
    return claimable
