from datetime import date
from decimal import Decimal
import unittest
from unittest.mock import patch

from typer.testing import CliRunner
from app.cli import app


class RatesCliTests(unittest.TestCase):
    @patch("app.db.SessionLocal")
    @patch("app.cli.get_rates")
    @patch("app.cli.date")
    def test_days_and_continue_after_failed_lookup(self, clock, fetch, sessions):
        clock.today.return_value = date(2026, 1, 5)
        def lookup(db, requested):
            if requested == date(2026, 1, 3):
                raise ValueError("API unavailable")
            return dict(requested_date=requested, rate_date=date(2026, 1, 2),
                        rates={"GBP": Decimal("1"), "EUR": Decimal("0.85"), "USD": Decimal("0.75")})
        fetch.side_effect = lookup
        result = CliRunner().invoke(app, ["get-rates", "--days", "3"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual([call.args[1] for call in fetch.call_args_list],
                         [date(2026, 1, 4), date(2026, 1, 3), date(2026, 1, 2)])
        self.assertIn("Skipped 2026-01-03: API unavailable", result.output)
        self.assertIn("1 USD = 0.7500000000 GBP", result.output)

    def test_invalid_days(self):
        result = CliRunner().invoke(app, ["get-rates", "--days", "0"])
        self.assertEqual(result.exit_code, 2)
