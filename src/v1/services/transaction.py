from chauff_cmn.models import User
from prisma import Prisma
from prisma.models import Currency

from ..errors import CurrencyNotFoundError, CurrencyValueError, WalletNotFoundError
from ..services.log import add_record, add_record_by_id
from ..services.idempotency import store_idempotency_key


async def add_to_wallet_by_id(tx: Prisma, user_id: int, amount: int, currency: Currency):
    wallet = await tx.wallet.find_unique(
        where = {
            "currencyId_userId": {
                "currencyId": currency.id,
                "userId": user_id,
            }
        }
    )
    if not wallet:
        await tx.wallet.create(
            {"balance": int(amount), "currencyId": currency.id, "userId": user_id}
        )
        return
    await tx.wallet.update(
        where = {
            "currencyId_userId": {
                "currencyId": currency.id,
                "userId": user_id
            }
        },
        data = {
            "balance": wallet.balance + amount
        }
    )


async def remove_from_wallet_by_id(tx: Prisma, user_id: int, amount: int, currency: Currency):
    wallet = await tx.wallet.find_unique(
        where = {
            "currencyId_userId": {
                "currencyId": currency.id,
                "userId": user_id,
            }
        }
    )
    if not wallet:
        raise WalletNotFoundError()

    await tx.wallet.update(
        where = {
            "currencyId_userId": {
                "currencyId": currency.id,
                "userId": user_id
            }
        },
        data = {
            "balance": wallet.balance - amount
        }
    )


async def add_to_wallet(tx: Prisma, user: User, amount: int, currency: Currency):
    return await add_to_wallet_by_id(tx, int(user.user_id), amount, currency)


async def remove_from_wallet(tx: Prisma, user: User, amount: int, currency: Currency):
    return await remove_from_wallet_by_id(tx, int(user.user_id), amount, currency)


async def credit_wallet(tx: Prisma, user: User, amount: int, currency_name: str, source: str, reason: str):
    if amount <= 0:
        raise CurrencyValueError("Value must be strictly positive.")

    currency = await tx.currency.find_unique(where = {"name": currency_name})
    if not currency:
        raise CurrencyNotFoundError()

    await add_record(tx, user, source, "wallet", reason, amount, currency)
    return await add_to_wallet(tx, user, amount, currency)


async def credit(prisma: Prisma, user: User, amount: int, currency_name: str, source: str, reason: str, idempotency_key: str, status_code: int):
    async with prisma.tx() as tx:
        await credit_wallet(tx, user, amount, currency_name, source, reason)
        await store_idempotency_key(tx, idempotency_key, int(user.user_id), status_code)


async def burn_wallet(tx: Prisma, user: User, amount: int, currency_name: str, destination: str, reason: str):
    if amount <= 0:
        raise CurrencyValueError("Value must be strictly positive.")

    currency = await tx.currency.find_unique(where = {"name": currency_name})
    if not currency:
        raise CurrencyNotFoundError()

    await add_record(tx, user, "wallet", destination, reason, amount, currency)
    return await remove_from_wallet(tx, user, amount, currency)


async def burn(prisma: Prisma, user: User, amount: int, currency_name: str, destination: str, reason: str, idempotency_key: str, status_code: int):
    async with prisma.tx() as tx:
        await burn_wallet(tx, user, amount, currency_name, destination, reason)
        await store_idempotency_key(tx, idempotency_key, int(user.user_id), status_code)


async def transfer_wallet(tx: Prisma, from_user_id: int, to_user_id: int, amount: int, currency_name: str, reason: str):
    """Mouvement direct entre deux comptes, sans passer par un utilisateur authentifié.

    Sert au règlement des paris (bataille -> escrow -> gagnants) : les comptes
    escrow sont des pseudo-comptes système (userId négatif, ex: -battleId pour
    escrow:battle:{battleId}), qui n'ont ni JWT ni session. Le débit et le crédit
    se font dans la même transaction Postgres passée par l'appelant : si le débit
    échoue (solde insuffisant -> contrainte CHECK), tout est annulé, l'un ne peut
    jamais arriver sans l'autre.
    """
    if amount <= 0:
        raise CurrencyValueError("Value must be strictly positive.")

    currency = await tx.currency.find_unique(where = {"name": currency_name})
    if not currency:
        raise CurrencyNotFoundError()

    await add_record_by_id(tx, from_user_id, "wallet", str(to_user_id), reason, amount, currency)
    await remove_from_wallet_by_id(tx, from_user_id, amount, currency)
    await add_record_by_id(tx, to_user_id, str(from_user_id), "wallet", reason, amount, currency)
    await add_to_wallet_by_id(tx, to_user_id, amount, currency)


async def transfer(prisma: Prisma, from_user_id: int, to_user_id: int, amount: int, currency_name: str, reason: str, idempotency_key: str, status_code: int):
    async with prisma.tx() as tx:
        await transfer_wallet(tx, from_user_id, to_user_id, amount, currency_name, reason)
        await store_idempotency_key(tx, idempotency_key, from_user_id, status_code)
