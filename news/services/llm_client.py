import json

import requests
from django.conf import settings


class LLMError(RuntimeError):
    """Raised on any LLM failure: connection refused, timeout, bad JSON."""


def call_local_llm(prompt, *, system="", json_mode=True, timeout=120):
    """Call a chat model through the cloud API (Groq).

    Function names stay the same on purpose: the judge and the writer
    keep calling call_local_llm - only the phone line behind it changed.
    """
    api_url = getattr(settings, "LLM_API_URL", "")
    api_key = getattr(settings, "LLM_API_KEY", "")
    model = getattr(settings, "LLM_MODEL", "")

    if not api_key:
        raise LLMError("LLM_API_KEY is missing - add it to local_secrets.py")

    headers = {"Authorization": f"Bearer {api_key}"}

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 1500,
    }

    try:
        resp = requests.post(api_url, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise LLMError(f"LLM API request failed: {exc}")

    try:
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMError(f"unexpected LLM API response: {exc}")

    if not text:
        raise LLMError("LLM API returned an empty response")
    return text


def call_local_llm_json(prompt, *, system="", timeout=120):
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
            raise LLMError(f"LLM returned invalid JSON: {exc}")
