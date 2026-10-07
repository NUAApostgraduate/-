import json
import os
import shutil
import threading
import time
import unittest
import uuid
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

import server
from verification_tools import verify_cangjie_artifact


TEST_ROOT = Path(__file__).resolve().parent


class SmallProjectMigrationTests(unittest.TestCase):
    def setUp(self):
        self.output_root = TEST_ROOT / f"_small_project_test_{uuid.uuid4().hex}"
        self.output_root.mkdir()

    def tearDown(self):
        self.output_root.resolve().relative_to(TEST_ROOT)
        shutil.rmtree(self.output_root)

    def test_two_source_files_create_downloadable_project_after_transient_failure(self):
        files = [
            {"path": "pom.xml", "language": "XML", "content": "<project/>", "lines": 1},
            {"path": "README.md", "language": "Markdown", "content": "A small project", "lines": 1},
            {"path": "src/main/java/Main.java", "language": "Java", "content": "class Main {}", "lines": 1},
            {"path": "src/main/java/Helper.java", "language": "Java", "content": "class Helper {}", "lines": 1},
        ]
        calls = []

        def model(config, messages, **kwargs):
            role = messages[0]["content"]
            calls.append(role)
            if len(calls) == 1:
                raise ConnectionError("temporary disconnect")
            target = messages[1]["content"].split("Target path: ", 1)[1].splitlines()[0]
            return f"// file: {target}\n```cangjie\nmain() {{ println(\"ok\") }}\n```"

        config = {"provider": "openai_compatible", "output_root": str(self.output_root), "cangjie_compiler": "missing-cjc"}
        build = {"attempted": True, "build_verified": False, "status": "compiler_unavailable", "log": "SDK unavailable"}
        with patch.object(server, "call_model", side_effect=model), \
             patch.object(server.time, "sleep") as sleep, \
             patch.object(server, "verify_cangjie_artifact", return_value=build):
            result = server.run_project_file_by_file(config, "", "java", "agent", files)

        self.assertEqual(len(calls), 3)
        self.assertTrue(all("file translator" in role for role in calls))
        sleep.assert_called_once_with(1)
        artifact = result["artifact"]
        self.assertTrue(artifact["download_url"])
        with zipfile.ZipFile(Path(artifact["output_dir"]) / "translated_project.zip") as archive:
            self.assertEqual(set(archive.namelist()), {
                "src/Main.cj", "src/Helper.cj", "cjpm.toml", "README.md"
            })
            self.assertIn('output-type = "executable"', archive.read("cjpm.toml").decode())
            self.assertEqual(archive.read("README.md"), b"A small project")

    def test_missing_file_block_cannot_be_reported_as_completed(self):
        files = [{"path": "src/main/java/Main.java", "language": "Java", "content": "class Main {}", "lines": 1}]
        with patch.object(server, "call_model", return_value="Here is an idea, but no generated file."):
            with self.assertRaisesRegex(ValueError, "缺少有效"):
                server.run_project_file_by_file({"provider": "openai_compatible", "output_root": str(self.output_root)}, "", "java", "agent", files)
        self.assertFalse(list(self.output_root.iterdir()))

    def test_whole_project_uses_one_model_request_for_all_sources(self):
        files = [
            {"path": "src/main/java/Main.java", "language": "Java", "content": "class Main { public static void main(String[] a) {} }", "lines": 1},
            {"path": "src/main/java/Helper.java", "language": "Java", "content": "class Helper { static int add(int a, int b) { return a+b; } }", "lines": 1},
            {"path": "README.md", "language": "Text", "content": "small project", "lines": 1},
        ]
        calls = []

        def model(config, messages, **kwargs):
            calls.append(messages[-1]["content"])
            return "// file: src/Main.cj\nmain() { println(\"ok\") }\n// file: src/Helper.cj\npublic func add(a: Int32, b: Int32): Int32 { return a + b }"

        build = {"attempted": True, "build_verified": True, "status": "passed", "log": "cjpm build success"}
        config = {"provider": "openai_compatible", "output_root": str(self.output_root), "cangjie_compiler": "missing-cjc"}
        with patch.object(server, "call_model", side_effect=model), \
             patch.object(server, "verify_cangjie_artifact", return_value=build):
            result = server.run_project_as_whole(config, "", "java", "whole-project", files)
        self.assertEqual(len(calls), 1)
        self.assertIn("src/main/java/Main.java", calls[0])
        self.assertIn("src/main/java/Helper.java", calls[0])
        self.assertTrue(result["artifact"]["validation"]["build_verified"])
        with zipfile.ZipFile(Path(result["artifact"]["output_dir"]) / "translated_project.zip") as archive:
            self.assertEqual(set(archive.namelist()), {"src/Main.cj", "src/Helper.cj", "cjpm.toml", "README.md"})

    def test_whole_project_rejects_incomplete_or_oversized_input(self):
        files = [{"path": "src/main/java/Main.java", "language": "Java", "content": "class Main {}", "lines": 1},
                 {"path": "src/main/java/Helper.java", "language": "Java", "content": "class Helper {}", "lines": 1}]
        config = {"provider": "openai_compatible", "output_root": str(self.output_root)}
        with patch.object(server, "call_model", return_value="// file: src/Main.cj\nmain() {}"):
            with self.assertRaisesRegex(ValueError, "缺少：src/helper.cj"):
                server.run_project_as_whole(config, "", "java", "whole-project", files)
        self.assertFalse(list(self.output_root.iterdir()))
        files[0]["content"] = "x" * (server.WHOLE_PROJECT_MAX_SOURCE_CHARS + 1)
        with patch.object(server, "call_model") as model:
            with self.assertRaisesRegex(ValueError, "输入上限"):
                server.run_project_as_whole(config, "", "java", "whole-project", files)
            model.assert_not_called()
        many_files = [{"path": f"src/main/java/File{index}.java", "language": "Java", "content": f"class File{index} {{}}"}
                      for index in range(server.WHOLE_PROJECT_MAX_SOURCE_FILES + 1)]
        with self.assertRaisesRegex(ValueError, "源码文件"):
            server.run_project_as_whole(config, "", "java", "whole-project", many_files)

    def test_completed_file_is_checkpointed_if_next_file_fails(self):
        files = [{"path": f"src/main/java/{name}.java", "language": "Java", "content": f"class {name} {{}}", "lines": 1}
                 for name in ("Main", "Helper")]
        checkpoint = self.output_root / "checkpoint"
        outputs = ["// file: src/Main.cj\nmain() {}", RuntimeError("model unavailable")]
        progress = []
        with patch.object(server, "call_model", side_effect=outputs):
            with self.assertRaisesRegex(RuntimeError, "model unavailable"):
                server.run_project_file_by_file({"provider": "openai_compatible", "output_root": str(self.output_root)},
                                                "", "java", "agent", files,
                                                lambda stage, done, total, current: progress.append((stage, done, total)), checkpoint)
        self.assertTrue((checkpoint / "src" / "Main.cj").is_file())
        self.assertFalse((checkpoint / "src" / "Helper.cj").exists())
        self.assertIn(("translating", 1, 2), progress)

    def test_nested_only_sources_do_not_get_false_build_success(self):
        (self.output_root / "src" / "app").mkdir(parents=True)
        (self.output_root / "src" / "app" / "Main.cj").write_text("main() {}", encoding="utf-8")
        (self.output_root / "cjpm.toml").write_text("[package]", encoding="utf-8")
        with patch("verification_tools.shutil.which", return_value="cjpm"):
            result = verify_cangjie_artifact(str(self.output_root))
        self.assertEqual(result["status"], "source_missing")
        self.assertFalse(result["build_verified"])

    def test_project_without_cjpm_is_not_verified_by_one_file_compilation(self):
        (self.output_root / "src").mkdir()
        (self.output_root / "src" / "main.cj").write_text("main() {}", encoding="utf-8")
        (self.output_root / "cjpm.toml").write_text("[package]", encoding="utf-8")
        with patch("verification_tools.shutil.which", side_effect=lambda command: None if command == "cjpm" else "cjc"):
            result = verify_cangjie_artifact(str(self.output_root))
        self.assertEqual(result["status"], "compiler_unavailable")
        self.assertFalse(result["build_verified"])

    def test_java_package_path_maps_into_root_source_package(self):
        self.assertEqual(server.map_to_cangjie_path("src/main/java/app/Main.java"), "src/app_Main.cj")
        self.assertEqual(server.map_to_cangjie_path("src/test/java/app/MainTest.java"), "tests/app_MainTest.cj")
        self.assertIn("main() {", server.normalize_cangjie_package("public static func main(args: Array<String>) {\n}", "src/Main.cj"))

    def test_translate_request_uses_openai_compatible_http_and_returns_zip(self):
        class ModelHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                prompt = request["messages"][-1]["content"]
                if "Target path:" in prompt:
                    target = prompt.split("Target path: ", 1)[1].splitlines()[0]
                    content = f'// file: {target}\nmain() {{ println("ok") }}'
                else:
                    content = "ok"
                payload = json.dumps({"id": "test", "object": "chat.completion", "created": 0,
                                      "model": "mock", "choices": [{"index": 0, "message":
                                      {"role": "assistant", "content": content}, "finish_reason": "stop"}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        http = ThreadingHTTPServer(("127.0.0.1", 0), ModelHandler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            config = {"provider": "openai_compatible", "java_snippet_provider": "local_model",
                      "model": "mock", "openai_base_url": f"http://127.0.0.1:{http.server_port}/v1",
                      "openai_enable_thinking": False, "output_root": str(self.output_root),
                      "cangjie_compiler": "missing-cjc", "cangjie_project_build": "missing-cjpm build",
                      "repo": ""}
            request = {"source_code": "class Main {}", "source_lang": "java", "task_type": "project",
                       "repair": False, "project_files": [{"path": "src/main/java/Main.java", "language": "Java",
                                                        "content": "class Main {}"}]}
            build = {"attempted": True, "build_verified": False, "status": "compiler_unavailable", "log": "SDK unavailable"}
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), \
                 patch.object(server, "get_config", return_value=config), \
                 patch.object(server, "verify_cangjie_artifact", return_value=build):
                result = server.translate_payload(request)
            self.assertTrue(result["ok"])
            self.assertTrue(result["artifact"]["download_url"])
            with zipfile.ZipFile(Path(result["artifact"]["output_dir"]) / "translated_project.zip") as archive:
                self.assertIn("src/Main.cj", archive.namelist())
                self.assertIn("package translated_project", archive.read("src/Main.cj").decode())
        finally:
            http.shutdown()
            http.server_close()
            thread.join()

    def test_project_job_returns_immediately_and_reports_each_completed_file(self):
        gate = threading.Event()
        calls = []
        config = {"provider": "openai_compatible", "java_snippet_provider": "local_model", "model": "mock",
                  "openai_base_url": "http://127.0.0.1/unused", "output_root": str(self.output_root),
                  "cangjie_compiler": "missing-cjc", "cangjie_project_build": "missing-cjpm build", "repo": ""}
        build = {"attempted": True, "build_verified": False, "status": "compiler_unavailable", "log": "SDK unavailable"}

        def model(config, messages, **kwargs):
            calls.append(messages[0]["content"])
            if len(calls) == 1:
                gate.wait(5)
            target = messages[1]["content"].split("Target path: ", 1)[1].splitlines()[0]
            return f'// file: {target}\nmain() {{ println("ok") }}'

        request = {"source_code": "class Main {}", "source_lang": "java", "task_type": "project", "repair": False,
                   "project_files": [{"path": f"src/main/java/{name}.java", "language": "Java", "content": f"class {name} {{}}"}
                                     for name in ("Main", "Helper")]}
        http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        job_id = ""
        try:
            with patch.object(server, "get_config", return_value=config), \
                 patch.object(server, "configured_provider_missing_credentials", return_value=[]), \
                 patch.object(server, "call_model", side_effect=model), \
                 patch.object(server, "verify_cangjie_artifact", return_value=build), \
                 patch.object(server, "save_translation_history", return_value="test-history"):
                base = f"http://127.0.0.1:{http.server_port}"
                post = Request(base + "/project-jobs", data=json.dumps(request).encode(),
                               headers={"Content-Type": "application/json"}, method="POST")
                with urlopen(post, timeout=3) as response:
                    started = json.load(response)
                    self.assertEqual(response.status, 202)
                job_id = started["job_id"]
                self.assertEqual(started["total_files"], 2)
                with urlopen(base + f"/project-jobs/{job_id}", timeout=3) as response:
                    self.assertLessEqual(json.load(response)["completed_files"], 1)
                gate.set()
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    with urlopen(base + f"/project-jobs/{job_id}", timeout=3) as response:
                        progress = json.load(response)
                    if progress["status"] == "completed":
                        break
                    time.sleep(0.05)
                self.assertEqual(progress["status"], "completed")
                self.assertEqual(progress["completed_files"], 2)
                self.assertTrue(progress["result"]["artifact"]["download_url"])
                self.assertEqual(len(calls), 2)
                self.assertTrue((self.output_root / "_project_jobs" / job_id / "src" / "Main.cj").is_file())
        finally:
            gate.set()
            http.shutdown()
            http.server_close()
            thread.join()
            if job_id:
                server.PROJECT_JOBS.pop(job_id, None)


if __name__ == "__main__":
    unittest.main()
