from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any


GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
USER_AGENT = "global-ai-weekly/0.1 (+https://github.com/iccm-stack/0806-)"


class GroqError(RuntimeError):
    pass


class GroqClient:
    def __init__(self, api_key: str | None = None, timeout: int = 90) -> None:
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self.timeout = timeout
        if not self.api_key:
            raise GroqError("GROQ_API_KEY environment variable is required")

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.1,
        max_tokens: int = 7000,
    ) -> dict[str, Any]:
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        # User-Agent is deliberately explicit: Groq is fronted by Cloudflare and
        # requests without it can be rejected with 403 / error 1010.
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        request = urllib.request.Request(GROQ_URL, data=body, headers=headers, method="POST")

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    result = json.loads(response.read().decode("utf-8"))
                content = result["choices"][0]["message"]["content"]
                return _parse_json_object(content)
            except urllib.error.HTTPError as exc:
                detail = exc.read(2000).decode("utf-8", "replace").strip()
                last_error = GroqError(f"HTTP {exc.code}: {detail or exc.reason}")
                if attempt < 2 and (exc.code == 429 or exc.code >= 500):
                    time.sleep(2**attempt)
                    continue
                break
            except (urllib.error.URLError, KeyError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(2**attempt)
        raise GroqError(f"Groq request failed after retries: {last_error}")


def _parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        text = text[first_newline + 1 :] if first_newline >= 0 else text
        if text.endswith("```"):
            text = text[:-3]
    value = json.loads(text.strip())
    if not isinstance(value, dict):
        raise json.JSONDecodeError("Expected a JSON object", text, 0)
    return value
