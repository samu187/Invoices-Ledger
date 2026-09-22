"""Offline validation/service/CLI checks; no connection to the user's database."""

from datetime import datetime, timezone
import unittest
import io
from contextlib import redirect_stderr
from unittest.mock import MagicMock, patch

from pydantic import ValidationError
from sqlalchemy.exc import OperationalError
from typer.testing import CliRunner

from app.cli import app, main
from app.schemas import SupplierCreate, SupplierRead
from app.services.suppliers import create_supplier


class SupplierTests(unittest.TestCase):
    def test_name_trimmed_and_invalid_names_rejected(self):
        self.assertEqual(SupplierCreate(name="  Acme Ltd  ").name, "Acme Ltd")
        for name in ("", "  ", "x" * 201):
            with self.subTest(name=name), self.assertRaises(ValidationError):
                SupplierCreate(name=name)
        with self.assertRaises(ValidationError):
            SupplierCreate(name="Acme", company_id=99)

    @patch("app.db.SessionLocal")
    def test_invalid_input_does_not_connect(self, get_engine):
        result = CliRunner().invoke(app, ["suppliers", "add", "--name", "   "])
        self.assertIsInstance(result.exception, ValidationError)
        get_engine.assert_not_called()

    @patch("app.cli.create_supplier")
    @patch("app.db.SessionLocal")
    def test_prompt_passes_validated_input_to_service(self, get_engine, create):
        create.return_value = SupplierRead(id=7, company_id=1, name="Acme", created_at=datetime.now(timezone.utc))
        result = CliRunner().invoke(app, ["suppliers", "add"], input="  Acme  \n")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(create.call_args.args[1].name, "Acme")
        self.assertIn("Created supplier #7: Acme", result.output)
        get_engine.return_value.__exit__.assert_called_once()

    def test_missing_company_never_inserts_supplier(self):
        session = MagicMock()
        session.get.return_value = None
        with self.assertRaises(ValueError):
            create_supplier(session, SupplierCreate(name="Acme"))
        session.add.assert_not_called()
        self.assertIs(session.begin.return_value.__exit__.call_args.args[0], ValueError)

    def test_flush_failure_propagates_through_transaction_for_rollback(self):
        session = MagicMock()
        session.flush.side_effect = OperationalError("insert", {}, RuntimeError("failure"))
        with self.assertRaises(OperationalError):
            create_supplier(session, SupplierCreate(name="Acme"))
        self.assertIs(session.begin.return_value.__exit__.call_args.args[0], OperationalError)

    @patch("app.cli.list_suppliers", return_value=[])
    @patch("app.db.SessionLocal")
    def test_empty_list_is_clear(self, engine, listing):
        result = CliRunner().invoke(app, ["suppliers", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No suppliers yet", result.output)

    @patch("app.cli.app", side_effect=OperationalError("secret SQL", {}, RuntimeError("secret password")))
    def test_database_error_is_reported_without_credentials(self, command):
        output = io.StringIO()
        with redirect_stderr(output), self.assertRaises(SystemExit) as error:
            main()
        self.assertEqual(error.exception.code, 1)
        self.assertIn("Database operation failed", output.getvalue())
        self.assertNotIn("secret", output.getvalue())

    @patch("app.cli.app")
    def test_validation_error_is_reported_once(self, command):
        try:
            SupplierCreate(name=" ")
        except ValidationError as error:
            command.side_effect = error
        output = io.StringIO()
        with redirect_stderr(output), self.assertRaises(SystemExit) as error:
            main()
        self.assertEqual(error.exception.code, 2)
        self.assertIn("name:", output.getvalue())


if __name__ == "__main__":
    unittest.main()
