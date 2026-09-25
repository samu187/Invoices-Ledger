"""The CLI Excel file contains the same P&L figures as the shared report."""

from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from openpyxl import load_workbook
from typer.testing import CliRunner

from app.cli import app


class PnlExportTests(TestCase):
    @patch("app.cli.SessionLocal")
    @patch("app.cli.get_profit_and_loss")
    def test_cli_exports_typed_dates_and_amounts(self, get_report, sessions):
        get_report.return_value = {
            "rows": [
                {"code": "4000", "name": "Sales", "account_type": "income", "profit": Decimal("125.50")},
                {"code": "5000", "name": "Office expense", "account_type": "expense", "profit": Decimal("-25.25")},
            ],
            "profit": Decimal("100.25"),
        }
        with TemporaryDirectory() as directory:
            path = Path(directory) / "pnl.xlsx"
            result = CliRunner().invoke(app, ["accounts", "pnl", "--from", "2026-01-01",
                                              "--to", "2026-01-31", "--export", str(path)])
            self.assertEqual(result.exit_code, 0, result.output)
            sheet = load_workbook(path, data_only=True).active
            self.assertEqual(sheet["A1"].value, "Profit and loss (GBP)")
            self.assertEqual(sheet["B2"].value.date().isoformat(), "2026-01-01")
            self.assertEqual(sheet["D6"].value, 125.5)
            self.assertEqual(sheet["D7"].value, -25.25)
            self.assertEqual(sheet["D8"].value, 100.25)
            self.assertIn("Net profit: GBP 100.25", result.output)
