"""Tests unitaires des schémas Pydantic de validation des payloads."""
import pytest
from pydantic import ValidationError

from src.v1.schemas.transactionPayload import BurnPayload, CreditPayload, TransferPayload


class TestCreditPayload:
    def test_valide(self):
        p = CreditPayload(
            amount=100,
            currency="HEAT",
            source="system",
            reason="reward",
            idempotencyKey="idem-credit-1",
        )
        assert p.amount == 100
        assert p.currency == "HEAT"
        assert p.source == "system"
        assert p.reason == "reward"

    def test_champ_manquant_leve_une_erreur(self):
        with pytest.raises(ValidationError):
            CreditPayload(amount=100, currency="HEAT", source="system")  # reason manquant

    def test_amount_doit_etre_un_entier(self):
        with pytest.raises(ValidationError):
            CreditPayload(amount="pas_un_int", currency="HEAT", source="s", reason="r")

    def test_amount_negatif_accepte(self):
        """Pydantic ne contraint pas le signe ; c'est à la couche service de valider."""
        p = CreditPayload(
            amount=-10,
            currency="HEAT",
            source="s",
            reason="r",
            idempotencyKey="idem-credit-2",
        )
        assert p.amount == -10


class TestBurnPayload:
    def test_valide(self):
        p = BurnPayload(
            amount=50,
            currency="HEAT",
            destination="burned",
            reason="penalty",
            idempotencyKey="idem-burn-1",
        )
        assert p.amount == 50
        assert p.destination == "burned"

    def test_champ_manquant_leve_une_erreur(self):
        with pytest.raises(ValidationError):
            BurnPayload(amount=50, currency="HEAT", reason="penalty")  # destination manquant

    def test_amount_doit_etre_un_entier(self):
        with pytest.raises(ValidationError):
            BurnPayload(amount=3.14, currency="HEAT", destination="d", reason="r")


class TestTransferPayload:
    def test_valide(self):
        p = TransferPayload(
            amount=100,
            currency="HEAT",
            fromUserId=42,
            toUserId=-42,
            reason="bet placed",
            idempotencyKey="bet:42:abc",
        )
        assert p.fromUserId == 42
        assert p.toUserId == -42

    def test_userid_negatif_accepte(self):
        """Les comptes système/escrow vivent sous un userId négatif."""
        p = TransferPayload(
            amount=100,
            currency="HEAT",
            fromUserId=-42,
            toUserId=7,
            reason="settle",
            idempotencyKey="settle:42:7",
        )
        assert p.fromUserId == -42

    def test_champ_manquant_leve_une_erreur(self):
        with pytest.raises(ValidationError):
            TransferPayload(amount=100, currency="HEAT", fromUserId=1, toUserId=2, reason="r")
