"""Rejoue exactement le contrôle fait par la route POST /transfer (check
idempotence -> transfer -> enregistrement de la clé) pour vérifier qu'un
retry avec la même clé (ex: client qui a vu un timeout côté réseau alors que
le serveur avait déjà traité la requête) ne crédite/débite jamais deux fois.
"""
from prisma import Prisma

from src.v1.services.idempotency import get_idempotency_status, store_idempotency_key
from src.v1.services.transaction import transfer_wallet


async def _wallet_balance(tx: Prisma, currency_id: str, user_id: int) -> int | None:
    wallet = await tx.wallet.find_unique(
        where={"currencyId_userId": {"currencyId": currency_id, "userId": user_id}}
    )
    return wallet.balance if wallet else None


async def _handle_transfer(prisma_tx: Prisma, key: str, from_user_id: int, to_user_id: int, amount: int, currency: str):
    """Reproduit le corps de POST /transfer : miroir volontaire du handler.

    En production, la route ouvre sa propre `prisma.tx()` ; ici le fixture
    `prisma_tx` est déjà une transaction (elle wrappe chaque test pour
    rollback automatique) donc on l'utilise directement plutôt que d'en
    imbriquer une deuxième, ce que Prisma Python déconseille explicitement.
    """
    existing_status = await get_idempotency_status(prisma_tx, key, from_user_id)
    if existing_status is not None:
        return existing_status

    await transfer_wallet(prisma_tx, from_user_id, to_user_id, amount, currency, "bet placed")
    await store_idempotency_key(prisma_tx, key, from_user_id, 204)
    return 204


class TestTransferIdempotency:
    async def test_rejeu_avec_la_meme_cle_ne_credite_qu_une_fois(self, prisma_tx: Prisma):
        currency = await prisma_tx.currency.create(
            {"name": "IDEMP_TEST_1", "claimRate": 1, "claimLimit": 100}
        )
        await prisma_tx.wallet.create({"balance": 200, "currencyId": currency.id, "userId": 40})

        key = "bet:1:some-bet-id"

        first = await _handle_transfer(prisma_tx, key, 40, -40, 80, "IDEMP_TEST_1")
        # Simule un client qui rejoue après avoir vu (ou cru voir) un échec
        # réseau, alors que le serveur avait déjà traité la première requête.
        second = await _handle_transfer(prisma_tx, key, 40, -40, 80, "IDEMP_TEST_1")

        assert first == 204
        assert second == 204
        assert await _wallet_balance(prisma_tx, currency.id, 40) == 120
        assert await _wallet_balance(prisma_tx, currency.id, -40) == 80

    async def test_deux_cles_differentes_creditent_deux_fois(self, prisma_tx: Prisma):
        currency = await prisma_tx.currency.create(
            {"name": "IDEMP_TEST_2", "claimRate": 1, "claimLimit": 100}
        )
        await prisma_tx.wallet.create({"balance": 200, "currencyId": currency.id, "userId": 41})

        await _handle_transfer(prisma_tx, "bet:2:bet-a", 41, -41, 30, "IDEMP_TEST_2")
        await _handle_transfer(prisma_tx, "bet:2:bet-b", 41, -41, 30, "IDEMP_TEST_2")

        assert await _wallet_balance(prisma_tx, currency.id, 41) == 140
        assert await _wallet_balance(prisma_tx, currency.id, -41) == 60
