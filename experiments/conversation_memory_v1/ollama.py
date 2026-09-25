"""Small audited HTTP adapter; never downloads a model or retries a generation."""
from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request

import numpy as np


def digest_json(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def validate_chat(response, options, expected_model=None):
    if not response.get("done") or response.get("done_reason") != "stop":
        raise RuntimeError("Incomplete/truncated model generation; retain failure and stop")
    if expected_model is not None and response.get("model") != expected_model:
        raise RuntimeError("Response model differs from the pinned request model")
    if not isinstance(response.get("message", {}).get("content"), str):
        raise ValueError("Missing model answer")
    prompt_count = response.get("prompt_eval_count")
    if not isinstance(prompt_count, int) or prompt_count + options["num_predict"] >= options["num_ctx"]:
        raise RuntimeError("Missing token accounting or unsafe prompt/context margin")


class Ollama:
    def __init__(self, base_url="http://localhost:11434", timeout=180):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def request(self, endpoint, payload=None):
        data = None if payload is None else json.dumps(payload, allow_nan=False).encode()
        request = urllib.request.Request(self.base_url + endpoint, data=data,
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.load(response)
        except (OSError, ValueError, urllib.error.URLError) as exc:
            raise RuntimeError(f"Ollama {endpoint} failed ({type(exc).__name__}); no automatic retry") from exc

    def identity(self, reader, embedder):
        version = self.request("/api/version")["version"]
        tags = self.request("/api/tags")["models"]
        models = {}
        for role, name in (("reader", reader), ("embedder", embedder)):
            matched = [m for m in tags if m.get("name") == name or m.get("model") == name]
            if len(matched) != 1 or not matched[0].get("digest"):
                raise ValueError(f"Specify an exact installed model name including tag: {name}")
            info = self.request("/api/show", {"model": name})
            if info.get("remote_host") or matched[0].get("remote_host"):
                raise ValueError("This protocol requires local model weights; cloud model aliases are not supported")
            models[role] = {"name": name, "digest": matched[0]["digest"],
                            "size": matched[0].get("size"), "show_sha256": digest_json(info)}
        return {"ollama_version": version, "models": models}

    def embed(self, name, texts):
        response = self.request("/api/embed", {"model": name, "input": texts,
                                                "truncate": False, "keep_alive": "10m"})
        if response.get("model") != name:
            raise ValueError("Embedding response model differs from the pinned request model")
        values = np.asarray(response["embeddings"], dtype=np.float64)
        if (values.ndim != 2 or values.shape[0] != len(texts) or values.shape[1] < 2
                or not np.all(np.isfinite(values)) or np.any(np.linalg.norm(values, axis=1) <= 1e-12)):
            raise ValueError("Invalid or zero embedding response")
        return values, response

    def chat(self, name, messages, options, *, json_output=False):
        payload = {"model": name, "messages": messages, "options": options,
                   "stream": False, "keep_alive": "10m"}
        if json_output:
            payload["format"] = "json"
        # Caller journals the raw response before validating completion/token
        # accounting, so even rejected generations remain inspectable.
        return self.request("/api/chat", payload)
