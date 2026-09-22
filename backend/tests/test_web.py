"""Web-shell checks with mocked database setup; no live database access."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from fastapi.staticfiles import StaticFiles
from typer.testing import CliRunner

from app.cli import app as cli
from app.main import app


class WebTests(unittest.TestCase):
    @patch("app.db.engine")
    @patch("app.db.seed_database", return_value=False)
    @patch("app.db.SessionLocal")
    @patch("app.db.initialize_database")
    def test_startup_setup_and_placeholder(self, initialize, sessions, seed, engine):
        with TemporaryDirectory() as directory, patch("app.main.STATIC_DIR", Path(directory)):
            with TestClient(app) as client:
                response = client.get("/")
                self.assertEqual(response.status_code, 200)
                self.assertIn("frontend will be added", response.text)
                self.assertEqual(client.get("/api/missing").status_code, 404)
                initialize.assert_called_once()
                seed.assert_called_once_with(sessions.return_value.__enter__.return_value)
        engine.dispose.assert_called_once()

    @patch("app.db.engine")
    @patch("app.db.initialize_database", side_effect=RuntimeError("setup failed"))
    @patch("app.db.seed_database")
    def test_setup_failure_stops_startup(self, seed, initialize, engine):
        with self.assertRaisesRegex(RuntimeError, "setup failed"):
            with TestClient(app):
                pass
        seed.assert_not_called()
        engine.dispose.assert_called_once()

    def test_built_homepage_and_static_files(self):
        # Without the context manager TestClient does not run database lifespan.
        with TemporaryDirectory() as directory, patch("app.main.STATIC_DIR", Path(directory)):
            Path(directory, "index.html").write_text('<h1>Built frontend</h1>')
            Path(directory, "bundle.js").write_text('console.log("demo")')
            mount = next((route for route in app.routes if getattr(route, "name", None) == "static"), None)
            if mount is None:
                app.mount("/static", StaticFiles(directory=directory), name="static")
                mount = app.routes[-1]
                self.addCleanup(app.routes.remove, mount)
            with patch.object(mount, "app", StaticFiles(directory=directory)):
                client = TestClient(app)
                self.assertIn("Built frontend", client.get("/").text)
                self.assertEqual(client.get("/static/bundle.js").status_code, 200)
                self.assertEqual(client.get("/static/missing.js").status_code, 404)
                client.close()

    @patch("uvicorn.run")
    def test_cli_starts_main_app(self, run):
        result = CliRunner().invoke(cli, ["web", "--port", "8010"])
        self.assertEqual(result.exit_code, 0, result.output)
        run.assert_called_once_with("app.main:app", host="127.0.0.1", port=8010)
