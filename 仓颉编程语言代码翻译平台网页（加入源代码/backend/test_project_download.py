import shutil
import threading
import unittest
import uuid
import zipfile
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

import server


ARTIFACT_ID = "project_migration_20261006_120000_a1b2c3d4"
TEST_ROOT = Path(__file__).resolve().parent


@contextmanager
def project_test_directory():
    # Use inherited workspace permissions instead of Python 3.13's restrictive
    # temporary-directory ACL, which is inaccessible in the Windows sandbox.
    directory = TEST_ROOT / f"_project_download_test_{uuid.uuid4().hex}"
    directory.mkdir()
    try:
        yield str(directory)
    finally:
        directory.resolve().relative_to(TEST_ROOT)
        shutil.rmtree(directory)


class ProjectDownloadTests(unittest.TestCase):
    def test_legacy_project_can_be_packaged_when_history_is_opened(self):
        with project_test_directory() as directory:
            artifact_dir = Path(directory) / ARTIFACT_ID
            (artifact_dir / "src").mkdir(parents=True)
            (artifact_dir / "src/main.cj").write_text("main() {}", encoding="utf-8")
            old_artifact = {"output_dir": str(artifact_dir), "files": ["src/main.cj"]}
            restored = server.restore_project_download(old_artifact, {"output_root": directory})
            self.assertEqual(restored["download_url"], f"/artifacts/{ARTIFACT_ID}/download")
            self.assertTrue((artifact_dir / "translated_project.zip").is_file())
            self.assertEqual(server.restore_project_download(restored, {"output_root": directory})["download_size"], restored["download_size"])

    def test_archive_preserves_paths_and_current_file_contents(self):
        with project_test_directory() as directory:
            artifact_dir = Path(directory) / ARTIFACT_ID
            (artifact_dir / "src").mkdir(parents=True)
            (artifact_dir / "src/main.cj").write_text("main() { println(\"完成\") }", encoding="utf-8")
            (artifact_dir / "cjpm.toml").write_text("[package]", encoding="utf-8")
            (artifact_dir / "migration_output.txt").write_text("internal report", encoding="utf-8")
            result = server.package_project_artifact(artifact_dir, ["src/main.cj", "cjpm.toml"])
            archive_path = server.resolve_project_download(ARTIFACT_ID, {"output_root": directory})
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(set(archive.namelist()), {"src/main.cj", "cjpm.toml"})
                self.assertIn("完成", archive.read("src/main.cj").decode("utf-8"))
            self.assertEqual(result["download_url"], f"/artifacts/{ARTIFACT_ID}/download")
            self.assertGreater(result["download_size"], 0)

    def test_artifact_is_packaged_after_compiler_repair(self):
        with project_test_directory() as directory:
            build = {"attempted": True, "build_verified": False}

            def repair(config, artifact_dir, files, initial_build):
                (artifact_dir / "src/main.cj").write_text("repaired code", encoding="utf-8")
                return {"final_build": {"attempted": True, "build_verified": True}}

            with patch.object(server, "compiler_status", return_value={"status": "available"}), \
                 patch.object(server, "verify_cangjie_artifact", return_value=build), \
                 patch.object(server, "repair_artifact_from_compiler", side_effect=repair):
                result = server.write_generated_artifact(
                    "project_migration", [{"path": "src/main.cj", "content": "original code"}],
                    "report", {"output_root": directory},
                )
            with zipfile.ZipFile(Path(result["output_dir"]) / "translated_project.zip") as archive:
                self.assertEqual(archive.read("src/main.cj"), b"repaired code")

    def test_invalid_and_missing_downloads_are_rejected(self):
        with project_test_directory() as directory:
            for artifact_id in ["../private", "C:/private", "ui_migration_20261006_120000_a1b2c3d4"]:
                with self.assertRaises(ValueError):
                    server.resolve_project_download(artifact_id, {"output_root": directory})
            with self.assertRaises(FileNotFoundError):
                server.resolve_project_download(ARTIFACT_ID, {"output_root": directory})

    def test_http_download_returns_zip_and_attachment_headers(self):
        with project_test_directory() as directory:
            artifact_dir = Path(directory) / ARTIFACT_ID
            artifact_dir.mkdir()
            (artifact_dir / "main.cj").write_text("main() {}", encoding="utf-8")
            server.package_project_artifact(artifact_dir, ["main.cj"])
            with patch.object(server, "get_config", return_value={"output_root": directory}), \
                 patch.object(server.Handler, "log_message"):
                http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
                thread = threading.Thread(target=http.serve_forever, daemon=True)
                thread.start()
                try:
                    base = f"http://127.0.0.1:{http.server_port}"
                    with urlopen(f"{base}/artifacts/{ARTIFACT_ID}/download") as response:
                        self.assertEqual(response.headers["Content-Type"], "application/zip")
                        self.assertIn("attachment", response.headers["Content-Disposition"])
                        self.assertTrue(response.read().startswith(b"PK"))
                    with self.assertRaises(HTTPError) as missing:
                        urlopen(f"{base}/artifacts/invalid/download")
                    self.assertEqual(missing.exception.code, 404)
                finally:
                    http.shutdown()
                    http.server_close()
                    thread.join()


if __name__ == "__main__":
    unittest.main()
