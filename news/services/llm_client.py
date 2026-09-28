import json

import requests
from django.conf import settings


class LLMError(RuntimeError):
    """Raised on any LLM failure: connection refused, timeout, bad JSON."""


def call_local_llm(prompt, *, system="", json_mode=True, timeout=600):
    base_url = getattr(settings, "LOCAL_LLM_BASE_URL", "http://localhost:11434")
    model = getattr(settings, "LOCAL_LLM_MODEL", "llama3.1")

    try:
        payload = {"model": model, "prompt": prompt, "system": system, "stream": False, "think": False}
        if json_mode:
            payload["format"] = "json"
        resp = requests.post(f"{base_url}/api/generate", json=payload, timeout=timeout)

        if resp.status_code == 404:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            chat_payload = {"model": model, "messages": messages, "stream": False, "think": False}
            if json_mode:
                chat_payload["format"] = "json"
            resp = requests.post(f"{base_url}/api/chat", json=chat_payload, timeout=timeout)

        resp.raise_for_status()
    except requests.RequestException as exc:
        raise LLMError(f"local LLM request failed: {exc}")

    data = resp.json()
    text = data.get("response") or data.get("message", {}).get("content", "")
    if not text:
        raise LLMError("local LLM returned an empty response")
    return text


def call_local_llm_json(prompt, *, system="", timeout=600):
    raw = call_local_llm(prompt, system=system, json_mode=True, timeout=timeout)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        cleaned = raw.strip()
        for fence in ("```json", "```"):
            if cleaned.startswith(fence):
                cleaned = cleaned[len(fence):]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        try:
            return json.loads(cleaned.strip())
        except json.JSONDecodeError as exc:
            raise LLMError(f"local LLM returned invalid JSON: {exc}")
