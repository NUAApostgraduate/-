import os
import unittest
from unittest.mock import patch

import server


JAVA_CODE = "public class Add { public static int add(int a, int b) { return a + b; } }"


class LocalSnippetRoutingTests(unittest.TestCase):
    def test_only_java_snippets_use_local_model(self):
        config = {"provider": "openai_compatible", "java_snippet_provider": "local_model"}
        self.assertEqual(server.config_for_translation(config, "java", "snippet")["provider"], "local_model")
        self.assertEqual(server.config_for_translation(config, "java", "project")["provider"], "openai_compatible")
        self.assertEqual(server.config_for_translation(config, "python", "snippet")["provider"], "openai_compatible")
        self.assertEqual(config["provider"], "openai_compatible")

    def test_java_snippet_never_calls_online_translation(self):
        with patch.object(server, "translate_with_local_model", return_value="func add(a: Int64, b: Int64): Int64 { return a + b }") as local:
            with patch.object(server, "translate_with_model", side_effect=AssertionError("online translation called")):
                with patch.object(server, "call_model", side_effect=AssertionError("online model called")):
                    result = server.translate_payload({"source_code": JAVA_CODE, "source_lang": "java", "task_type": "snippet", "repair": False})
        self.assertEqual(result["provider"], "local_model")
        self.assertTrue(result["translation"].startswith("func add"))
        local.assert_called_once()

    @unittest.skipUnless(os.environ.get("RUN_LOCAL_MODEL_SMOKE") == "1", "Set RUN_LOCAL_MODEL_SMOKE=1 to load the trained weights")
    def test_real_local_model(self):
        result = server.translate_payload({"source_code": JAVA_CODE, "source_lang": "java", "task_type": "snippet", "repair": True})
        self.assertEqual(result["provider"], "local_model")
        self.assertTrue(result["translation"].strip())
        print("\nLocal model output:", result["translation"][:500])


if __name__ == "__main__":
    unittest.main()
