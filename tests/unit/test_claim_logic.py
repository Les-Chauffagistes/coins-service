"""Tests unitaires de la fonction pure _compute_claimable."""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from src.v1.services.claim import _compute_claimable


def _currency(claim_rate: int, claim_limit: int):
    c = MagicMock()
    c.claimRate = claim_rate
    c.claimLimit = claim_limit
    return c


def _claim(last_claim_at: datetime):
    c = MagicMock()
    c.lastClaimAt = last_claim_at
    return c


class TestComputeClaimable:
    def test_aucun_claim_precedent_retourne_la_limite(self):
        """Sans historique de claim, on obtient directement claimLimit."""
        currency = _currency(claim_rate=10, claim_limit=100)
        result = _compute_claimable(datetime.now(timezone.utc), None, currency)
        assert result == 100

    def test_accumulation_lineaire(self):
        """Les tokens s'accumulent au rythme de claimRate par seconde."""
        currency = _currency(claim_rate=1, claim_limit=1000)
        now = datetime.now(timezone.utc)
        last = _claim(now - timedelta(seconds=50))
        assert _compute_claimable(now, last, currency) == 50

    def test_plafonnement_par_claim_limit(self):
        """On ne peut jamais dépasser claimLimit, même après longtemps."""
        currency = _currency(claim_rate=10, claim_limit=100)
        now = datetime.now(timezone.utc)
        last = _claim(now - timedelta(seconds=10_000))
        assert _compute_claimable(now, last, currency) == 100

    def test_zero_secondes_ecoulees(self):
        """Claim immédiat après le précédent → 0 tokens."""
        currency = _currency(claim_rate=10, claim_limit=100)
        now = datetime.now(timezone.utc)
        last = _claim(now)
        assert _compute_claimable(now, last, currency) == 0

    def test_partie_decimale_tronquee(self):
        """int() tronque : 1.9 s × 1 rate = 1 token (pas 2)."""
        currency = _currency(claim_rate=1, claim_limit=1000)
        now = datetime.now(timezone.utc)
        last = _claim(now - timedelta(seconds=1, milliseconds=900))
        assert _compute_claimable(now, last, currency) == 1

    def test_claim_rate_eleve(self):
        """Vérifie que rate × secondes est bien borné par la limite."""
        currency = _currency(claim_rate=100, claim_limit=500)
        now = datetime.now(timezone.utc)
        # 3 s × 100 = 300, en-dessous du plafond
        last = _claim(now - timedelta(seconds=3))
        assert _compute_claimable(now, last, currency) == 300
