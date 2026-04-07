"""Tests d'intégration pour src/v1/services/transaction.py"""
import pytest
from authentication_types.models import User
from prisma import Prisma

from src.v1.services.transaction import credit_wallet, burn_wallet


def _user(user_id: int = 1) -> User:
    return User(user_id=str(user_id), pseudo="testuser")


async def _wallet_balance(tx: Prisma, currency_id: str, user_id: int) -> int | None:
    wallet = await tx.wallet.find_unique(
        where={"currencyId_userId": {"currencyId": currency_id, "userId": user_id}}
    )
    return wallet.balance if wallet else None


class TestCreditWallet:
    async def test_cree_un_wallet_et_credite(self, prisma_tx: Prisma):
        await prisma_tx.currency.create(
            {"name": "CREDIT_TEST_1", "claimRate": 1, "claimLimit": 100}
        )
        user = _user(10)
        await credit_wallet(prisma_tx, user, 50, "CREDIT_TEST_1", "system", "reward")

        currency = await prisma_tx.currency.find_unique(where={"name": "CREDIT_TEST_1"})
        balance = await _wallet_balance(prisma_tx, currency.id, 10)
        assert balance == 50

    async def test_credite_un_wallet_existant(self, prisma_tx: Prisma):
        currency = await prisma_tx.currency.create(
            {"name": "CREDIT_TEST_2", "claimRate": 1, "claimLimit": 100}
        )
        await prisma_tx.wallet.create({"balance": 100, "currencyId": currency.id, "userId": 11})

        await credit_wallet(prisma_tx, _user(11), 50, "CREDIT_TEST_2", "system", "reward")

        balance = await _wallet_balance(prisma_tx, currency.id, 11)
        assert balance == 150

    async def test_leve_value_error_si_devise_inconnue(self, prisma_tx: Prisma):
        with pytest.raises(ValueError):
            await credit_wallet(prisma_tx, _user(1), 10, "DEVISE_INCONNUE", "src", "reason")

    async def test_credit_cree_un_log(self, prisma_tx: Prisma):
        currency = await prisma_tx.currency.create(
            {"name": "CREDIT_TEST_3", "claimRate": 1, "claimLimit": 100}
        )
        await credit_wallet(prisma_tx, _user(12), 30, "CREDIT_TEST_3", "source_test", "raison_test")

        logs = await prisma_tx.log.find_many(
            where={"currencyId": currency.id, "userId": 12}
        )
        assert len(logs) == 1
        assert logs[0].fromState == "source_test"
        assert logs[0].toState == "wallet"
        assert logs[0].amount == 30


class TestBurnWallet:
    async def test_retire_du_solde(self, prisma_tx: Prisma):
        currency = await prisma_tx.currency.create(
            {"name": "BURN_TEST_1", "claimRate": 1, "claimLimit": 100}
        )
        await prisma_tx.wallet.create({"balance": 200, "currencyId": currency.id, "userId": 20})

        await burn_wallet(prisma_tx, _user(20), 80, "BURN_TEST_1", "burned", "penalty")

        balance = await _wallet_balance(prisma_tx, currency.id, 20)
        assert balance == 120

    async def test_leve_value_error_si_wallet_absent(self, prisma_tx: Prisma):
        await prisma_tx.currency.create(
            {"name": "BURN_TEST_2", "claimRate": 1, "claimLimit": 100}
        )
        with pytest.raises(ValueError, match="Wallet not found"):
            await burn_wallet(prisma_tx, _user(999), 10, "BURN_TEST_2", "dst", "reason")

    async def test_leve_value_error_si_devise_inconnue(self, prisma_tx: Prisma):
        with pytest.raises(ValueError):
            await burn_wallet(prisma_tx, _user(1), 10, "DEVISE_INCONNUE", "dst", "reason")

    async def test_burn_cree_un_log(self, prisma_tx: Prisma):
        currency = await prisma_tx.currency.create(
            {"name": "BURN_TEST_3", "claimRate": 1, "claimLimit": 100}
        )
        await prisma_tx.wallet.create({"balance": 100, "currencyId": currency.id, "userId": 21})

        await burn_wallet(prisma_tx, _user(21), 40, "BURN_TEST_3", "dest_test", "raison_test")

        logs = await prisma_tx.log.find_many(
            where={"currencyId": currency.id, "userId": 21}
        )
        assert len(logs) == 1
        assert logs[0].fromState == "wallet"
        assert logs[0].toState == "dest_test"
        assert logs[0].amount == 40
