"""Standard-library tests for launcher isolation and child lifecycle."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("portable_launcher", Path(__file__).with_name("launcher.py"))
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


class LauncherIsolationTests(unittest.TestCase):
    def test_only_package_ai_config_reaches_child(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            env_path = root / "review.env"
            env_path.write_text('DEEPSEEK_API_KEY="package-key"\nDB_PASSWORD=must-not-load\nDEEPSEEK_MODEL=model-a # comment\n', encoding="utf-8")
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "machine-secret", "PORTABLE_DEEPSEEK_API_KEY": "other-secret", "DATABASE_URL": "private-db", "PYTHONPATH": "host-packages"}):
                result = launcher.build_child_env(root, root / "data", "demo", 23456, "s" * 48, "t" * 48, launcher.read_review_env(env_path))
            self.assertEqual(result["PORTABLE_DEEPSEEK_API_KEY"], "package-key")
            self.assertEqual(result["PORTABLE_DEEPSEEK_MODEL"], "model-a")
            self.assertEqual(result["PYTHON_DOTENV_DISABLED"], "1")
            self.assertFalse({"DB_PASSWORD", "DEEPSEEK_API_KEY", "DATABASE_URL", "PYTHONPATH"} & result.keys())
            self.assertNotIn("machine-secret", result.values())
            self.assertNotIn("PORTABLE_DEEPSEEK_BASE_URL", result)

    def test_missing_review_env_does_not_inherit_key(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "host-secret"}):
            result = launcher.build_child_env(Path("/package"), Path("/data"), "demo", 23456, "s" * 48, "t" * 48, {})
        self.assertEqual(result["PORTABLE_DEEPSEEK_API_KEY"], "")

    def test_config_roundtrip_does_not_expand_shell_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "review.env"
            values = {"DEEPSEEK_API_KEY": 'key-$USER-`secret`-"-\\', "DEEPSEEK_BASE_URL": "https://example.invalid/v1", "UNRELATED": "ignore"}
            launcher.save_review_env(path, values)
            self.assertEqual(launcher.read_review_env(path), {key: value for key, value in values.items() if key in launcher.ENV_KEYS})
            with self.assertRaises(launcher.LauncherError):
                launcher.save_review_env(path, {"DEEPSEEK_API_KEY": "first\nsecond"})

    def test_package_identity_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "portable-manifest.json").write_text(json.dumps({"package_id": "../../outside"}))
            with self.assertRaises(launcher.LauncherError):
                launcher.package_identity(root)

    def test_instance_lock_is_released_by_owner(self):
        with tempfile.TemporaryDirectory() as temporary:
            first = launcher.InstanceLock(Path(temporary) / "instance.lock")
            second = launcher.InstanceLock(first.path)
            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
            first.close()
            self.assertTrue(second.acquire())
            second.close()

    def test_health_requires_both_package_and_random_token(self):
        payload = {"status": "ok", "package_id": "package-a", "instance_token": "a" * 48}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(payload).encode())

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            state = {**payload, "port": server.server_port}
            self.assertTrue(launcher.is_healthy(state, "package-a"))
            self.assertFalse(launcher.is_healthy({**state, "instance_token": "b" * 48}, "package-a"))
            self.assertFalse(launcher.is_healthy(state, "package-b"))
            self.assertFalse(launcher.is_healthy({**state, "port": "8000"}, "package-a"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_stop_uses_own_child_handle_without_touching_other_process(self):
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        own = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], **options)
        other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], **options)
        try:
            launcher.Controller.terminate_process(own)
            self.assertIsNotNone(own.poll())
            self.assertIsNone(other.poll())
        finally:
            launcher.Controller.terminate_process(own)
            launcher.Controller.terminate_process(other)

    @unittest.skipUnless(os.name == "nt", "Windows process job only")
    def test_windows_job_stops_assigned_child_on_close(self):
        job = launcher.WindowsChildJob()
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            job.add(child)
            job.close()
            child.wait(timeout=5)
            self.assertIsNotNone(child.poll())
        finally:
            job.close()
            launcher.Controller.terminate_process(child)

    def test_launcher_log_redacts_key_and_secret(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(os.environ, {"LOCALAPPDATA": temporary}):
                controller = launcher.Controller(Path(temporary), lambda *_: None)
            controller.redacted_values.update({"unique-private-key", "long-secret-value"})
            controller.log("upstream unique-private-key failed; long-secret-value")
            controller.log("Authorization: Bearer hidden-value")
            result = controller.log_path.read_text(encoding="utf-8")
            self.assertNotIn("unique-private-key", result)
            self.assertNotIn("long-secret-value", result)
            self.assertNotIn("hidden-value", result)


if __name__ == "__main__":
    unittest.main()
