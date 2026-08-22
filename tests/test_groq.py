import json
import os
import unittest
from unittest.mock import MagicMock, patch

from ai_weekly.groq import GROQ_MODEL, USER_AGENT, GroqClient, GroqError, _parse_json_object


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps({"choices": [{"message": {"content": '{"ok": true}'}}]}).encode()


class GroqClientTests(unittest.TestCase):
    def test_parses_json_from_markdown_or_explanation(self):
        self.assertEqual(_parse_json_object('Result:\n```json\n{"ok": true}\n```'), {"ok": True})

    def test_requires_environment_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(GroqError):
                GroqClient()

    @patch("urllib.request.urlopen", return_value=_Response())
    def test_model_and_user_agent_are_always_set(self, mocked_open):
        client = GroqClient(api_key="test-key")
        self.assertEqual(client.complete_json(system="s", user="u"), {"ok": True})
        request = mocked_open.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["model"], GROQ_MODEL)
        self.assertEqual(GROQ_MODEL, "openai/gpt-oss-120b")
        self.assertEqual(request.headers["User-agent"], USER_AGENT)
        self.assertEqual(request.headers["Authorization"], "Bearer test-key")


if __name__ == "__main__":
    unittest.main()
