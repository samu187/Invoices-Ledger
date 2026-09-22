"""Offline checks: these tests never connect to PostgreSQL."""

import os
import unittest
from unittest.mock import patch

from sqlalchemy import create_mock_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import configure_mappers
from typer.testing import CliRunner

from app.cli import app
from app.db import DatabaseConfigurationError, database_url
from app.models import Base


class DatabaseSetupTests(unittest.TestCase):
    def test_models_compile_for_postgresql(self):
        configure_mappers()
        statements = []
        engine = create_mock_engine("postgresql+psycopg://", lambda sql, *a, **kw: statements.append(str(sql.compile(dialect=postgresql.dialect()))))
        Base.metadata.create_all(engine, checkfirst=False)
        self.assertEqual(len(Base.metadata.tables), 9)
        ddl = "\n".join(statements)
        self.assertIn("NUMERIC(18, 2)", ddl)
        self.assertIn("FOREIGN KEY(payment_id, invoice_id)", ddl)
        self.assertIn("WHERE kind = 'invoice'", ddl)
        self.assertNotIn("DROP TABLE", ddl)

    @patch("app.db.load_dotenv")
    def test_hosted_url_normalized_without_losing_options(self, _):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://demo:secret@db:5432/ledger?sslmode=require"}):
            url = database_url()
        self.assertEqual(url.drivername, "postgresql+psycopg")
        self.assertEqual(url.query["sslmode"], "require")

    @patch("app.db.load_dotenv")
    def test_invalid_configuration_rejected(self, _):
        for value in ("", "sqlite:///demo.db", "not-a-url", "postgresql://"):
            with self.subTest(value=value), patch.dict(os.environ, {"DATABASE_URL": value}):
                with self.assertRaises(DatabaseConfigurationError):
                    database_url()

    @patch("app.cli.get_engine")
    def test_help_needs_no_database(self, engine):
        result = CliRunner().invoke(app, ["--help"])
        self.assertEqual(result.exit_code, 0)
        engine.assert_not_called()

    @patch("app.db.load_dotenv")
    def test_bad_configuration_cli_exits_cleanly(self, _):
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///secret-value"}):
            result = CliRunner().invoke(app, ["init-db"])
        self.assertEqual(result.exit_code, 1)
        self.assertNotIn("secret-value", result.output)
        self.assertIn("PostgreSQL", result.output)


if __name__ == "__main__":
    unittest.main()
