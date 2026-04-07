"""Tests d'intégration pour src/v1/services/balance.py"""
import pytest
from authentication_types.models import User
from prisma import Prisma

from src.v1.services.balance import get_balance


def _user(user_id: int = 1) -> User:
    return User(user_id=str(user_id), pseudo="testuser")


class TestGetBalance:
    async def test_retourne_zero_si_pas_de_wallet(self, prisma_tx: Prisma):
        await prisma_tx.currency.create(
            {"name": "BAL_TEST_1", "claimRate": 1, "claimLimit": 100}
        )
        result = await get_balance(prisma_tx, _user(999), "BAL_TEST_1")
        assert result == 0

    async def test_retourne_le_solde_du_wallet(self, prisma_tx: Prisma):
        currency = await prisma_tx.currency.create(
            {"name": "BAL_TEST_2", "claimRate": 1, "claimLimit": 100}
        )
        await prisma_tx.wallet.create(
            {"balance": 250, "currencyId": currency.id, "userId": 42}
        )
        result = await get_balance(prisma_tx, _user(42), "BAL_TEST_2")
        assert result == 250

    async def test_leve_value_error_si_devise_inconnue(self, prisma_tx: Prisma):
        with pytest.raises(ValueError):
            await get_balance(prisma_tx, _user(1), "DEVISE_INEXISTANTE")

    async def test_isolation_par_utilisateur(self, prisma_tx: Prisma):
        """Deux utilisateurs sur la même devise ont des soldes indépendants."""
        currency = await prisma_tx.currency.create(
            {"name": "BAL_TEST_3", "claimRate": 1, "claimLimit": 100}
        )
        await prisma_tx.wallet.create({"balance": 100, "currencyId": currency.id, "userId": 1})
        await prisma_tx.wallet.create({"balance": 200, "currencyId": currency.id, "userId": 2})

        assert await get_balance(prisma_tx, _user(1), "BAL_TEST_3") == 100
        assert await get_balance(prisma_tx, _user(2), "BAL_TEST_3") == 200
