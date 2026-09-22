"""Seed behaviour checks without connecting to PostgreSQL."""

from decimal import Decimal
import unittest
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner
from app.cli import app

from app.db import seed_database
from app.models import Base, Account, Company, JournalEntry, Supplier


class SeedTests(unittest.TestCase):
    def make_session(self):
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = "reference_data_v1"
        db.get.return_value = None
        db.scalar.return_value = None
        return db

    def test_reference_data_and_balanced_opening_journal(self):
        db = self.make_session()
        self.assertTrue(seed_database(db))
        records = [call.args[0] for call in db.add.call_args_list]
        self.assertEqual(sum(isinstance(row, Company) for row in records), 1)
        self.assertEqual(sum(isinstance(row, Account) for row in records), 12)
        self.assertEqual(sum(isinstance(row, Supplier) for row in records), 3)
        journal = next(row for row in records if isinstance(row, JournalEntry))
        self.assertEqual(journal.kind, "opening")
        self.assertEqual(sum(line.debit for line in journal.lines), Decimal("50000.00"))
        self.assertEqual(sum(line.credit for line in journal.lines), Decimal("50000.00"))
        self.assertIsNone(journal.invoice_id)
        self.assertIsNone(journal.payment_id)

    def test_completed_seed_does_not_add_anything(self):
        db = self.make_session()
        db.execute.return_value.scalar_one_or_none.return_value = None
        self.assertFalse(seed_database(db))
        db.add.assert_not_called()
        db.get.assert_not_called()

    def test_existing_reference_records_are_preserved(self):
        db = self.make_session()
        db.get.return_value = Company(id=1, name="Existing name", base_currency="GBP")
        types = ["asset", "asset", "liability", "equity", "income"] + ["expense"] * 7
        db.scalar.side_effect = [Account(id=i, company_id=1, account_type=t) for i, t in enumerate(types, 1)] + [Supplier(name="Existing")] * 3
        self.assertTrue(seed_database(db))
        records = [call.args[0] for call in db.add.call_args_list]
        self.assertEqual(len(records), 1)
        self.assertIsInstance(records[0], JournalEntry)
        self.assertEqual(db.get.return_value.name, "Existing name")

    def test_conflict_exits_transaction_with_error(self):
        db = self.make_session()
        db.scalar.return_value = Account(company_id=1, account_type="income")
        with self.assertRaisesRegex(ValueError, "1000"):
            seed_database(db)
        self.assertIs(db.begin.return_value.__exit__.call_args.args[0], ValueError)

    def test_reset_deletes_children_first_before_seeding(self):
        db = self.make_session()
        self.assertTrue(seed_database(db, reset=True))
        statements = [call.args[0] for call in db.execute.call_args_list]
        self.assertEqual([statement.table.name for statement in statements[:-1]],
                         [table.name for table in reversed(Base.metadata.sorted_tables)])
        self.assertTrue(all(statement.is_delete for statement in statements[:-1]))
        self.assertTrue(statements[-1].is_insert)
        db.begin.assert_called_once()

    def test_reset_failure_exits_same_transaction(self):
        db = self.make_session()
        db.flush.side_effect = RuntimeError("seed failed")
        with self.assertRaises(RuntimeError):
            seed_database(db, reset=True)
        self.assertIs(db.begin.return_value.__exit__.call_args.args[0], RuntimeError)

    @patch("app.db.SessionLocal")
    def test_declining_reset_does_not_open_session(self, factory):
        result = CliRunner().invoke(app, ["seed", "--reset"], input="n\n")
        self.assertNotEqual(result.exit_code, 0)
        factory.assert_not_called()

    @patch("app.db.seed_database", return_value=True)
    @patch("app.db.SessionLocal")
    def test_confirmed_reset_passes_flag(self, factory, seed):
        result = CliRunner().invoke(app, ["seed", "--reset"], input="y\n")
        self.assertEqual(result.exit_code, 0, result.output)
        seed.assert_called_once_with(factory.return_value.__enter__.return_value, reset=True)
