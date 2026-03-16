"""
DocForge — Ollama VLM Runtime
================================

Connects to a locally running Ollama server for Vision-Language Model
inference. Ollama is the recommended runtime — easiest setup, manages
model downloads, provides a simple REST API.

Setup:
  1. Install Ollama:  curl -fsSL https://ollama.ai/install.sh | sh
  2. Pull a VLM:      ollama pull minicpm-v
  3. Start server:    ollama serve  (or it runs automatically)
"""

from __future__ import annotations

import base64
import subprocess
import time
from pathlib import Path

import requests

from docforge.infra.logging import get_logger

logger = get_logger(__name__)


class OllamaRuntime:
    """VLM runtime using Ollama's local REST API.

    Communicates with Ollama via HTTP at http://127.0.0.1:11434.
    Supports multimodal models that accept image inputs.
    """

    def __init__(self, model: str, port: int = 11434, timeout: int = 120):
        """
        Args:
            model:   Ollama model name (e.g., "minicpm-v", "llava", "moondream").
            port:    Ollama server port.
            timeout: Request timeout in seconds.
        """
        self.model = model
        self.base_url = f"http://127.0.0.1:{port}"
        self.timeout = timeout

    def ensure_running(self) -> None:
        """Verify that Ollama is running and the required model is available.

        Raises:
            ConnectionError: If Ollama server is not reachable.
            RuntimeError: If the required model is not pulled.
        """
        # Check server connectivity
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
        except requests.ConnectionError:
            raise ConnectionError(
                "Ollama is not running. Start it with: ollama serve\n"
                "Install from: https://ollama.ai"
            )
        except requests.RequestException as exc:
            raise ConnectionError(f"Ollama server error: {exc}")

        # Check if model is available (compare both full name and base name)
        raw_models = [m["name"] for m in resp.json().get("models", [])]
        base_models = [n.split(":")[0] for n in raw_models]
        model_base = self.model.split(":")[0]
        if self.model not in raw_models and model_base not in base_models:
            logger.warning(
                "Model '%s' not found in Ollama. Available: %s",
                self.model, ", ".join(models) or "(none)",
            )
            raise RuntimeError(
                f"Model '{self.model}' not found in Ollama.\n"
                f"Pull it with: ollama pull {self.model}"
            )

        logger.info("Ollama ready — model: %s, server: %s", self.model, self.base_url)

    def complete_with_image(
        self,
        image_path: str,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> str:
        """Send an image + prompt to Ollama and return the text response.

        Args:
            image_path:  Path to the PNG image file.
            prompt:      Text prompt for the VLM.
            max_tokens:  Maximum tokens to generate.
            temperature: Sampling temperature (low = deterministic).

        Returns:
            The model's text response.

        Raises:
            TimeoutError: If inference exceeds the configured timeout.
            RuntimeError: If the API returns an error.
        """
        # Encode image as base64
        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")

        logger.debug(
            "  Ollama request: model=%s, image=%s, prompt_len=%d",
            self.model, Path(image_path).name, len(prompt),
        )

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "images": [image_b64],
                    "stream": True,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
                timeout=(10, self.timeout),  # (connect_timeout, read_timeout)
                stream=True,
            )
            response.raise_for_status()
        except requests.Timeout:
            raise TimeoutError(
                f"Ollama inference timed out after {self.timeout}s "
                f"(model={self.model})"
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Ollama API error: {exc}")

        # Stream response — allows Ctrl+C between chunks
        import json as _json
        text_parts: list[str] = []
        for line in response.iter_lines():
            if line:
                chunk = _json.loads(line)
                text_parts.append(chunk.get("response", ""))
                if chunk.get("done", False):
                    break

        text = "".join(text_parts)

        logger.debug(
            "  Ollama response: %d chars",
            len(text),
        )

        return text

    def pull_model(self, model: str | None = None) -> None:
        """Pull (download) a model via Ollama.

        Args:
            model: Model name to pull. Defaults to self.model.
        """
        target = model or self.model
        logger.info("Pulling Ollama model: %s (this may take several minutes)...", target)

        try:
            subprocess.run(
                ["ollama", "pull", target],
                check=True,
                timeout=1800,  # 30 minute timeout for large models
            )
            logger.info("Model '%s' pulled successfully", target)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"Failed to pull model '{target}': {exc}")
        except FileNotFoundError:
            raise RuntimeError(
                "Ollama command not found. Install from: https://ollama.ai"
            )

    def list_models(self) -> list[str]:
        """List all models available in the local Ollama instance.

        Returns:
            List of model name strings.
        """
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        except requests.RequestException:
            return []
