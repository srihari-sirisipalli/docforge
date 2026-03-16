"""
DocForge — llama.cpp VLM Runtime
==================================

Manages a local llama.cpp server process for VLM inference.
Provides fine-grained control over model quantisation, context length,
thread count, and GPU layer offloading.

Requires:
  - llama-cpp-python or llama-server binary
  - A GGUF-format multimodal model + multimodal projector file
"""

from __future__ import annotations

import base64
import subprocess
import time
from pathlib import Path
from typing import Optional

import requests

from docforge.infra.logging import get_logger

logger = get_logger(__name__)


class LlamaCppRuntime:
    """VLM runtime using a llama.cpp server with multimodal support.

    Starts a llama-server process, waits for it to be ready, then
    communicates via HTTP API for inference.
    """

    def __init__(
        self,
        model_path: str,
        mmproj_path: str = "",
        port: int = 8080,
        context_length: int = 4096,
        threads: int = 4,
        gpu_layers: int = 0,
        timeout: int = 120,
    ):
        self.model_path = model_path
        self.mmproj_path = mmproj_path
        self.port = port
        self.context_length = context_length
        self.threads = threads
        self.gpu_layers = gpu_layers
        self.timeout = timeout
        self.base_url = f"http://127.0.0.1:{port}"
        self.process: Optional[subprocess.Popen] = None

    def start_server(self) -> None:
        """Start the llama.cpp server with the configured model.

        Blocks until the server is ready to accept requests.

        Raises:
            FileNotFoundError: If llama-server binary is not found.
            TimeoutError: If the server doesn't start within 180 seconds.
        """
        cmd = [
            "llama-server",
            "--model", self.model_path,
            "--ctx-size", str(self.context_length),
            "--threads", str(self.threads),
            "--n-gpu-layers", str(self.gpu_layers),
            "--port", str(self.port),
        ]

        # Add multimodal projector if provided
        if self.mmproj_path:
            cmd.extend(["--mmproj", self.mmproj_path])

        logger.info(
            "Starting llama.cpp server: model=%s, threads=%d, gpu_layers=%d",
            Path(self.model_path).name, self.threads, self.gpu_layers,
        )

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for server readiness
        self._wait_for_ready(timeout=180)
        logger.info("llama.cpp server ready on port %d", self.port)

    def complete_with_image(
        self,
        image_path: str,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> str:
        """Send image + prompt to llama.cpp and return the response.

        Args:
            image_path:  Path to PNG image.
            prompt:      Text prompt.
            max_tokens:  Max tokens to generate.
            temperature: Sampling temperature.

        Returns:
            Model response text.
        """
        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")

        try:
            response = requests.post(
                f"{self.base_url}/completion",
                json={
                    "prompt": f"[img-1]\n{prompt}",
                    "image_data": [{"data": image_b64, "id": 1}],
                    "n_predict": max_tokens,
                    "temperature": temperature,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json().get("content", "")

        except requests.Timeout:
            raise TimeoutError(f"llama.cpp inference timed out after {self.timeout}s")
        except requests.RequestException as exc:
            raise RuntimeError(f"llama.cpp API error: {exc}")

    def stop(self) -> None:
        """Gracefully shut down the llama.cpp server process."""
        if self.process:
            logger.info("Stopping llama.cpp server...")
            self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None
            logger.info("llama.cpp server stopped")

    def ensure_running(self) -> None:
        """Check if the server is running and responsive."""
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=5)
            if resp.status_code != 200:
                raise ConnectionError("llama.cpp server not healthy")
        except requests.ConnectionError:
            raise ConnectionError("llama.cpp server is not running")

    def _wait_for_ready(self, timeout: int = 180) -> None:
        """Poll the server until it's ready or timeout expires."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                resp = requests.get(f"{self.base_url}/health", timeout=2)
                if resp.status_code == 200:
                    return
            except requests.ConnectionError:
                pass
            time.sleep(2)

        raise TimeoutError(
            f"llama.cpp server did not become ready within {timeout}s"
        )
