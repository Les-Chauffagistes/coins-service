"""Tests d'intégration pour src/v1/services/claim.py

Note : les fonctions `claim` et `get_claimable` ouvrent leur propre transaction
en interne. On leur passe donc `prisma_client` (session-scoped) plutôt que
`prisma_tx`. Chaque test utilise des noms de devise uniques pour éviter les
collisions, et nettoie ses données en fin d'exécution.
"""
import pytest
from datetime import datetime, timezone, timedelta
from authentication_types.models import User
from prisma import Prisma

from src.v1.services.claim import get_claimable, get_claimable_for_currency, claim


def _user(user_id: int = 1) -> User:
    return User(user_id=str(user_id), pseudo="testuser")


class TestGetClaimable:
    async def test_retourne_claim_limit_si_premier_claim(self, prisma_client: Prisma):
        currency = await prisma_client.currency.create(
            {"name": "CLAIMABLE_TEST_1", "claimRate": 10, "claimLimit": 500}
        )
        try:
            result = await get_claimable(prisma_client, _user(100), "CLAIMABLE_TEST_1")
            assert result == 500
        finally:
            await prisma_client.currency.delete(where={"id": currency.id})

    async def test_retourne_tokens_accumules(self, prisma_client: Prisma):
        currency = await prisma_client.currency.create(
            {"name": "CLAIMABLE_TEST_2", "claimRate": 1, "claimLimit": 10_000}
        )
        # Dernier claim il y a 60 secondes → 60 tokens attendus
        past = datetime.now(timezone.utc) - timedelta(seconds=60)
        await prisma_client.claim.create(
            {
                "currencyId": currency.id,
                "userId": 101,
                "lastClaimAt": past,
            }
        )
        try:
            result = await get_claimable(prisma_client, _user(101), "CLAIMABLE_TEST_2")
            assert result == 60
        finally:
            await prisma_client.claim.delete_many(where={"currencyId": currency.id})
            await prisma_client.currency.delete(where={"id": currency.id})

    async def test_plafonne_par_claim_limit(self, prisma_client: Prisma):
        currency = await prisma_client.currency.create(
            {"name": "CLAIMABLE_TEST_3", "claimRate": 100, "claimLimit": 200}
        )
        past = datetime.now(timezone.utc) - timedelta(seconds=10_000)
        await prisma_client.claim.create(
            {"currencyId": currency.id, "userId": 102, "lastClaimAt": past}
        )
        try:
            result = await get_claimable(prisma_client, _user(102), "CLAIMABLE_TEST_3")
            assert result == 200
        finally:
            await prisma_client.claim.delete_many(where={"currencyId": currency.id})
            await prisma_client.currency.delete(where={"id": currency.id})

    async def test_leve_value_error_si_devise_inconnue(self, prisma_client: Prisma):
        with pytest.raises(ValueError):
            await get_claimable(prisma_client, _user(1), "DEVISE_INEXISTANTE_XYZ")


class TestClaim:
    async def test_credite_le_wallet_et_retourne_le_montant(self, prisma_client: Prisma):
        currency = await prisma_client.currency.create(
            {"name": "CLAIM_TEST_1", "claimRate": 1, "claimLimit": 1000}
        )
        past = datetime.now(timezone.utc) - timedelta(seconds=100)
        await prisma_client.claim.create(
            {"currencyId": currency.id, "userId": 200, "lastClaimAt": past}
        )
        try:
            claimed = await claim(prisma_client, _user(200), "CLAIM_TEST_1")
            assert claimed == 100

            wallet = await prisma_client.wallet.find_unique(
                where={
                    "currencyId_userId": {"currencyId": currency.id, "userId": 200}
                }
            )
            assert wallet is not None
            assert wallet.balance == 100
        finally:
            await prisma_client.wallet.delete_many(where={"currencyId": currency.id})
            await prisma_client.claim.delete_many(where={"currencyId": currency.id})
            await prisma_client.currency.delete(where={"id": currency.id})

    async def test_met_a_jour_last_claim_at(self, prisma_client: Prisma):
        currency = await prisma_client.currency.create(
            {"name": "CLAIM_TEST_2", "claimRate": 1, "claimLimit": 1000}
        )
        past = datetime.now(timezone.utc) - timedelta(seconds=50)
        await prisma_client.claim.create(
            {"currencyId": currency.id, "userId": 201, "lastClaimAt": past}
        )
        before = datetime.now(timezone.utc)
        try:
            await claim(prisma_client, _user(201), "CLAIM_TEST_2")

            updated_claim = await prisma_client.claim.find_unique(
                where={
                    "currencyId_userId": {"currencyId": currency.id, "userId": 201}
                }
            )
            assert updated_claim.lastClaimAt >= before
        finally:
            await prisma_client.wallet.delete_many(where={"currencyId": currency.id})
            await prisma_client.claim.delete_many(where={"currencyId": currency.id})
            await prisma_client.currency.delete(where={"id": currency.id})

    async def test_claim_successif_accumule_correctement(self, prisma_client: Prisma):
        """Après un premier claim, le second n'accumule que depuis le dernier claim."""
        currency = await prisma_client.currency.create(
            {"name": "CLAIM_TEST_3", "claimRate": 1, "claimLimit": 10_000}
        )
        past = datetime.now(timezone.utc) - timedelta(seconds=30)
        await prisma_client.claim.create(
            {"currencyId": currency.id, "userId": 202, "lastClaimAt": past}
        )
        try:
            first = await claim(prisma_client, _user(202), "CLAIM_TEST_3")
            assert first == 30

            # Immédiatement après, presque rien ne s'est accumulé
            second = await claim(prisma_client, _user(202), "CLAIM_TEST_3")
            assert second < 2  # moins d'une seconde s'est écoulée
        finally:
            await prisma_client.wallet.delete_many(where={"currencyId": currency.id})
            await prisma_client.claim.delete_many(where={"currencyId": currency.id})
            await prisma_client.currency.delete(where={"id": currency.id})
