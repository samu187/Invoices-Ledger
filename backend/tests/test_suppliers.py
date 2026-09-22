"""Offline validation/service/CLI checks; no connection to the user's database."""

from datetime import datetime, timezone
import unittest
from unittest.mock import MagicMock, patch

from pydantic import ValidationError
from sqlalchemy.exc import OperationalError
from typer.testing import CliRunner

from app.cli import app
from app.schemas import SupplierCreate, SupplierRead
from app.services.suppliers import CompanyNotConfiguredError, create_supplier


class SupplierTests(unittest.TestCase):
    def test_name_trimmed_and_invalid_names_rejected(self):
        self.assertEqual(SupplierCreate(name="  Acme Ltd  ").name, "Acme Ltd")
        for name in ("", "  ", "x" * 201):
            with self.subTest(name=name), self.assertRaises(ValidationError):
                SupplierCreate(name=name)
        with self.assertRaises(ValidationError):
            SupplierCreate(name="Acme", company_id=99)

    @patch("app.cli.get_engine")
    def test_invalid_input_does_not_connect(self, get_engine):
        result = CliRunner().invoke(app, ["suppliers", "add", "--name", "   "])
        self.assertEqual(result.exit_code, 2)
        get_engine.assert_not_called()

    @patch("app.cli.create_supplier")
    @patch("app.cli.get_engine")
    def test_prompt_passes_validated_input_to_service(self, get_engine, create):
        create.return_value = SupplierRead(id=7, company_id=1, name="Acme", created_at=datetime.now(timezone.utc))
        result = CliRunner().invoke(app, ["suppliers", "add"], input="  Acme  \n")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(create.call_args.args[1].name, "Acme")
        self.assertIn("Created supplier #7: Acme", result.output)
        get_engine.return_value.dispose.assert_called_once()

    @patch("app.services.suppliers.Session")
    def test_missing_company_never_inserts_supplier(self, factory):
        session = factory.return_value.__enter__.return_value
        session.get.return_value = None
        with self.assertRaises(CompanyNotConfiguredError):
            create_supplier(MagicMock(), SupplierCreate(name="Acme"))
        session.add.assert_not_called()
        self.assertIs(session.begin.return_value.__exit__.call_args.args[0], CompanyNotConfiguredError)

    @patch("app.services.suppliers.Session")
    def test_flush_failure_propagates_through_transaction_for_rollback(self, factory):
        session = factory.return_value.__enter__.return_value
        session.flush.side_effect = OperationalError("insert", {}, RuntimeError("failure"))
        with self.assertRaises(OperationalError):
            create_supplier(MagicMock(), SupplierCreate(name="Acme"))
        self.assertIs(session.begin.return_value.__exit__.call_args.args[0], OperationalError)

    @patch("app.cli.list_suppliers", return_value=[])
    @patch("app.cli.get_engine")
    def test_empty_list_is_clear(self, engine, listing):
        result = CliRunner().invoke(app, ["suppliers", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No suppliers yet", result.output)

    @patch("app.cli.create_supplier", side_effect=OperationalError("secret SQL", {}, RuntimeError("secret password")))
    @patch("app.cli.get_engine")
    def test_failure_has_no_success_message_or_credentials(self, engine, create):
        result = CliRunner().invoke(app, ["suppliers", "add", "--name", "Acme"])
        self.assertEqual(result.exit_code, 1)
        self.assertNotIn("Created supplier", result.output)
        self.assertNotIn("secret", result.output)
        engine.return_value.dispose.assert_called_once()


if __name__ == "__main__":
    unittest.main()
