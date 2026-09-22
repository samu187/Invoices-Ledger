"""FX conversion and cache tests without live database or network calls."""

from datetime import date, timedelta
from decimal import Decimal as D
import json
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from app.models import FxRate
from app.services.fx_rates import fetch_rates, get_rates


class FxRateTests(unittest.TestCase):
    requested = date(2026, 1, 4)
    published = date(2026, 1, 2)

    def response(self, **changes):
        rows = [dict(date="2026-01-02", base="GBP", quote="EUR", rate=1.25),
                dict(date="2026-01-02", base="GBP", quote="USD", rate=1.50)]
        rows[1].update(changes)
        return rows

    def fetch(self, rows):
        with patch("app.services.fx_rates.urlopen") as open_url:
            open_url.return_value.__enter__.return_value.read.return_value = json.dumps(rows).encode()
            result = fetch_rates(self.requested)
            request = open_url.call_args.args[0]
            self.assertEqual(request.get_header("User-agent"), "InvoiceLedger/0.1")
            url = request.full_url
            self.assertIn("providers=boe", url)
            self.assertIn("base=GBP", url)
            self.assertIn("quotes=EUR%2CUSD", url)
            return result

    def test_inverted_rates_and_actual_publication_date(self):
        result = self.fetch(self.response())
        self.assertEqual(result["rates"], {"GBP": D("1"), "EUR": D("0.8"), "USD": D("0.6666666667")})
        self.assertEqual(result["rate_date"], self.published)
        self.assertEqual(result["requested_date"], self.requested)

    @patch("app.services.fx_rates.date")
    def test_today_requests_yesterday(self, clock):
        clock.today.return_value = date(2026, 1, 3)
        clock.fromisoformat.side_effect = date.fromisoformat
        with patch("app.services.fx_rates.urlopen") as open_url:
            open_url.return_value.__enter__.return_value.read.return_value = json.dumps(self.response()).encode()
            result = fetch_rates(date(2026, 1, 3))
            self.assertIn("date=2026-01-02", open_url.call_args.args[0].full_url)
            self.assertEqual(result["requested_date"], date(2026, 1, 3))
            self.assertEqual(result["rate_date"], date(2026, 1, 2))

    @patch("app.services.fx_rates.date")
    @patch("app.services.fx_rates.fetch_rates")
    def test_today_cache_uses_yesterday(self, fetch, clock):
        clock.today.return_value = date(2026, 1, 3)
        db = MagicMock()
        db.in_transaction.return_value = False
        db.scalars.return_value.all.return_value = self.cached(self.published)
        result = get_rates(db, date(2026, 1, 3))
        self.assertIn(self.published, db.scalars.call_args.args[0].compile().params.values())
        self.assertEqual(result["rate_date"], self.published)
        self.assertEqual(result["requested_date"], date(2026, 1, 3))
        fetch.assert_not_called()

    def test_incomplete_mismatched_stale_or_invalid_quotes_rejected(self):
        cases = [[], self.response()[:1], self.response(date="2026-01-01"),
                 self.response(quote="GBP"), self.response(base="USD"),
                 self.response(rate=0), self.response(rate=-1), self.response(rate="NaN"),
                 self.response(rate="Infinity"), self.response(rate="bad")]
        for day in ("2025-12-20", "2026-01-05"):
            rows = self.response(date=day)
            rows[0]["date"] = day
            cases.append(rows)
        for rows in cases:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.fetch(rows)

    @patch("app.services.fx_rates.urlopen", side_effect=HTTPError("https://api.frankfurter.dev", 403, "Forbidden", {}, None))
    def test_http_error_includes_status(self, open_url):
        with self.assertRaisesRegex(ValueError, "HTTP 403"):
            fetch_rates(self.requested)

    @patch("app.services.fx_rates.urlopen", side_effect=URLError("offline"))
    def test_network_error_is_clear(self, open_url):
        with self.assertRaisesRegex(ValueError, "Could not fetch"):
            fetch_rates(self.requested)

    @patch("app.services.fx_rates.urlopen")
    def test_future_date_does_not_call_api(self, open_url):
        with self.assertRaisesRegex(ValueError, "future"):
            fetch_rates(date.today() + timedelta(days=1))
        open_url.assert_not_called()

    def cached(self, rate_date):
        return [FxRate(currency=currency, base_currency="GBP", rate_date=rate_date, rate=rate)
                for currency, rate in {"GBP": D("1"), "EUR": D("0.8"), "USD": D("0.6666666667")}.items()]

    @patch("app.services.fx_rates.fetch_rates")
    def test_complete_cache_avoids_network(self, fetch):
        db = MagicMock()
        db.in_transaction.return_value = False
        db.scalars.return_value.all.return_value = self.cached(self.published)
        result = get_rates(db, self.published)
        self.assertEqual(set(result["rates"]), {"GBP", "EUR", "USD"})
        fetch.assert_not_called()
        db.execute.assert_not_called()

    @patch("app.services.fx_rates.fetch_rates")
    def test_existing_invoice_transaction_uses_savepoint_without_commit(self, fetch):
        db = MagicMock()
        db.in_transaction.return_value = True
        db.scalars.return_value.all.return_value = self.cached(self.published)
        get_rates(db, self.published)
        db.begin_nested.assert_called_once()
        db.begin.assert_not_called()
        db.commit.assert_not_called()
        fetch.assert_not_called()

    @patch("app.services.fx_rates.fetch_rates")
    def test_missing_or_partial_cache_inserts_three_actual_date_rows(self, fetch):
        for cached in ([], self.cached(self.requested)[:1]):
            db = MagicMock()
            db.in_transaction.return_value = False
            db.scalars.return_value.all.side_effect = [cached, self.cached(self.published)]
            fetch.return_value = dict(requested_date=self.requested, rate_date=self.published,
                                     base_currency="GBP", rates={row.currency: row.rate for row in self.cached(self.published)})
            result = get_rates(db, self.requested)
            statement = db.execute.call_args.args[0]
            params = statement.compile().params
            self.assertEqual({params[f"currency_m{i}"] for i in range(3)}, {"GBP", "EUR", "USD"})
            self.assertTrue(all(params[f"rate_date_m{i}"] == self.published for i in range(3)))
            self.assertIn("ON CONFLICT", str(statement))
            self.assertEqual(result["rate_date"], self.published)
            db.begin.assert_called_once()

    @patch("app.services.fx_rates.fetch_rates", side_effect=ValueError("Invalid rates"))
    def test_fetch_failure_saves_nothing(self, fetch):
        db = MagicMock()
        db.in_transaction.return_value = False
        db.scalars.return_value.all.return_value = []
        with self.assertRaisesRegex(ValueError, "Invalid rates"):
            get_rates(db, self.requested)
        db.execute.assert_not_called()
        self.assertIs(db.begin.return_value.__exit__.call_args.args[0], ValueError)
