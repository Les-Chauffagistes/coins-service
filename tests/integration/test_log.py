"""Tests d'intégration pour src/v1/services/log.py"""
from authentication_types.models import User
from prisma import Prisma

from src.v1.services.log import add_record


def _user(user_id: int = 1) -> User:
    return User(user_id=str(user_id), pseudo="testuser")


class TestAddRecord:
    async def test_cree_une_entree_de_log(self, prisma_tx: Prisma):
        currency = await prisma_tx.currency.create(
            {"name": "LOG_TEST_1", "claimRate": 1, "claimLimit": 100}
        )
        user = _user(1)

        log = await add_record(prisma_tx, user, "system", "wallet", "reward", 42, currency)

        assert log.amount == 42
        assert log.fromState == "system"
        assert log.toState == "wallet"
        assert log.reason == "reward"
        assert log.userId == 1
        assert log.currencyId == currency.id

    async def test_enregistre_le_bon_user_id(self, prisma_tx: Prisma):
        currency = await prisma_tx.currency.create(
            {"name": "LOG_TEST_2", "claimRate": 1, "claimLimit": 100}
        )
        user = _user(999)

        log = await add_record(prisma_tx, user, "src", "dst", "reason", 10, currency)

        assert log.userId == 999
