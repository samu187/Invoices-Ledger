"""Offline checks: these tests never connect to PostgreSQL."""

import os
import subprocess
import sys
from contextlib import contextmanager
import unittest
from unittest.mock import patch

from sqlalchemy import create_mock_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import configure_mappers
from typer.testing import CliRunner

from app.cli import app
from app.db import get_db
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

    def test_hosted_url_normalized_without_losing_options(self):
        result = subprocess.run(
            [sys.executable, "-c", "from app.db import engine; assert engine.url.drivername == 'postgresql+psycopg'; assert engine.url.query['sslmode'] == 'require'"],
            env={**os.environ, "DATABASE_URL": "postgresql://demo:secret@db:5432/ledger?sslmode=require"},
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_configuration_rejected_but_help_works(self):
        for value in ("", "sqlite:///secret-value", "not-a-url", "postgresql://"):
            env = {**os.environ, "DATABASE_URL": value}
            help_result = subprocess.run([sys.executable, "-m", "app.cli", "--help"], env=env, capture_output=True, text=True)
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            result = subprocess.run([sys.executable, "-m", "app.cli", "init-db"], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("PostgreSQL", result.stderr)
            self.assertNotIn("secret-value", result.stderr)

    @patch("app.db.SessionLocal")
    def test_help_needs_no_database(self, factory):
        result = CliRunner().invoke(app, ["--help"])
        self.assertEqual(result.exit_code, 0)
        factory.assert_not_called()

    @patch("app.db.SessionLocal")
    def test_session_closed_on_error(self, factory):
        with self.assertRaises(RuntimeError):
            with contextmanager(get_db)() as db:
                self.assertIs(db, factory.return_value.__enter__.return_value)
                raise RuntimeError("failed operation")
        factory.return_value.__exit__.assert_called_once()


if __name__ == "__main__":
    unittest.main()
