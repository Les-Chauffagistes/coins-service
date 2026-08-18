"""Tests d'intégration pour src/v1/services/claim.py

Note : les fonctions `claim` et `get_claimable` ouvrent leur propre transaction
en interne. On leur passe donc `prisma_client` (session-scoped) plutôt que
`prisma_tx`. Chaque test utilise des noms de devise uniques pour éviter les
collisions, et nettoie ses données en fin d'exécution.
"""
import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from authentication_types.models import User
from prisma import Prisma

from src.v1.services import claim as claim_module
from src.v1.services.claim import get_claimable, get_claimable_for_currency, claim, ClaimConflictError


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
            {"name": "CLAIMABLE_TEST_2", "claimRate": 60, "claimLimit": 10_000}
        )
        # Dernier claim il y a une heure → 60 tokens attendus
        past = datetime.now(timezone.utc) - timedelta(hours=1)
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
        past = datetime.now(timezone.utc) - timedelta(hours=10)
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
    async def test_premier_claim_cree_le_suivi_et_ne_peut_pas_etre_repete(
        self, prisma_client: Prisma
    ):
        currency = await prisma_client.currency.create(
            {"name": "CLAIM_TEST_FIRST", "claimRate": 120, "claimLimit": 120}
        )
        user = _user(199)
        try:
            first = await claim(prisma_client, user, "CLAIM_TEST_FIRST")
            second = await claim(prisma_client, user, "CLAIM_TEST_FIRST")

            claim_record = await prisma_client.claim.find_unique(
                where={
                    "currencyId_userId": {
                        "currencyId": currency.id,
                        "userId": 199,
                    }
                }
            )
            wallet = await prisma_client.wallet.find_unique(
                where={
                    "currencyId_userId": {
                        "currencyId": currency.id,
                        "userId": 199,
                    }
                }
            )

            assert first == 120
            assert second == 0
            assert claim_record is not None
            assert wallet is not None
            assert wallet.balance == 120
        finally:
            await prisma_client.wallet.delete_many(where={"currencyId": currency.id})
            await prisma_client.claim.delete_many(where={"currencyId": currency.id})
            await prisma_client.currency.delete(where={"id": currency.id})

    async def test_credite_le_wallet_et_retourne_le_montant(self, prisma_client: Prisma):
        currency = await prisma_client.currency.create(
            {"name": "CLAIM_TEST_1", "claimRate": 100, "claimLimit": 1000}
        )
        past = datetime.now(timezone.utc) - timedelta(hours=1)
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

    async def test_premier_claim_cree_la_ligne(self, prisma_client: Prisma):
        """Aucune ligne Claim préexistante : le premier claim doit la créer, pas planter."""
        currency = await prisma_client.currency.create(
            {"name": "CLAIM_TEST_FIRST", "claimRate": 1, "claimLimit": 500}
        )
        try:
            claimed = await claim(prisma_client, _user(210), "CLAIM_TEST_FIRST")
            assert claimed == 500  # aucun claim précédent -> claimLimit
        finally:
            await prisma_client.wallet.delete_many(where={"currencyId": currency.id})
            await prisma_client.claim.delete_many(where={"currencyId": currency.id})
            await prisma_client.currency.delete(where={"id": currency.id})

    async def test_claims_concurrents_ne_double_creditent_pas(self, prisma_client: Prisma):
        """Deux claims lancés en parallèle sur le même compte : un seul doit
        réussir, l'autre doit lever ClaimConflictError plutôt que de créditer
        deux fois le même montant (régression du double-claim, finding 1.2).

        `asyncio.gather` seul ne suffit pas à reproduire la course : sur des
        requêtes aussi rapides, la première tâche a le temps de lire, écrire
        et commit avant même que la seconde démarre (pas de vraie fenêtre de
        concurrence). On force donc explicitement le chevauchement : la
        première lecture de `last_claim` est retardée, le temps que le second
        claim termine tout son cycle lecture+écriture pendant ce délai.
        """
        currency = await prisma_client.currency.create(
            {"name": "CLAIM_TEST_RACE", "claimRate": 1, "claimLimit": 10_000}
        )
        past = datetime.now(timezone.utc) - timedelta(seconds=100)
        await prisma_client.claim.create(
            {"currencyId": currency.id, "userId": 211, "lastClaimAt": past}
        )

        real_get_last_claim = claim_module.get_last_claim
        first_read_started = asyncio.Event()

        async def delayed_get_last_claim(db, user, currency):
            result = await real_get_last_claim(db, user, currency)
            if not first_read_started.is_set():
                first_read_started.set()
                # Laisse l'autre claim() terminer tout son cycle (lecture +
                # CAS + commit) avant que celui-ci ne poursuive avec la
                # valeur de last_claim qu'il vient de lire.
                await asyncio.sleep(0.3)
            return result

        try:
            with patch.object(claim_module, "get_last_claim", side_effect=delayed_get_last_claim):
                results = await asyncio.gather(
                    claim(prisma_client, _user(211), "CLAIM_TEST_RACE"),
                    claim(prisma_client, _user(211), "CLAIM_TEST_RACE"),
                    return_exceptions=True,
                )

            for r in results:
                if isinstance(r, Exception) and not isinstance(r, ClaimConflictError):
                    raise r
            successes = [r for r in results if not isinstance(r, Exception)]
            conflicts = [r for r in results if isinstance(r, ClaimConflictError)]
            assert len(successes) == 1
            assert len(conflicts) == 1

            wallet = await prisma_client.wallet.find_unique(
                where={"currencyId_userId": {"currencyId": currency.id, "userId": 211}}
            )
            assert wallet.balance == successes[0]
        finally:
            await prisma_client.wallet.delete_many(where={"currencyId": currency.id})
            await prisma_client.claim.delete_many(where={"currencyId": currency.id})
            await prisma_client.currency.delete(where={"id": currency.id})

    async def test_claim_successif_accumule_correctement(self, prisma_client: Prisma):
        """Après un premier claim, le second n'accumule que depuis le dernier claim."""
        currency = await prisma_client.currency.create(
            {"name": "CLAIM_TEST_3", "claimRate": 60, "claimLimit": 10_000}
        )
        past = datetime.now(timezone.utc) - timedelta(minutes=30)
        await prisma_client.claim.create(
            {"currencyId": currency.id, "userId": 202, "lastClaimAt": past}
        )
        try:
            first = await claim(prisma_client, _user(202), "CLAIM_TEST_3")
            assert first == 30

            # Immédiatement après, aucun coin entier ne s'est accumulé
            second = await claim(prisma_client, _user(202), "CLAIM_TEST_3")
            assert second == 0
        finally:
            await prisma_client.wallet.delete_many(where={"currencyId": currency.id})
            await prisma_client.claim.delete_many(where={"currencyId": currency.id})
            await prisma_client.currency.delete(where={"id": currency.id})
