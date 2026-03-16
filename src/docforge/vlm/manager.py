"""
DocForge — Model Manager
==========================

Unified lifecycle management for VLM runtimes. Handles:
  - Runtime selection (Ollama, llama.cpp, Transformers)
  - Model startup and health checking
  - Fallback hierarchy (primary model → fallback model → heuristic-only)
  - Graceful shutdown
"""

from __future__ import annotations

from docforge.infra.config import VLMConfig
from docforge.infra.logging import get_logger

logger = get_logger(__name__)


class ModelManager:
    """Manages VLM runtime lifecycles.

    Initialises the appropriate runtime based on configuration, handles
    startup/shutdown, and provides health checking.
    """

    def __init__(self, config: VLMConfig):
        self.config = config
        self.runtime = None
        self._started = False

    def start(self) -> None:
        """Start the configured VLM runtime.

        Attempts the primary model first. If it fails, tries the fallback.

        Raises:
            RuntimeError: If no VLM runtime could be started.
        """
        if not self.config.enabled:
            logger.info("VLM is disabled in configuration")
            return

        logger.info(
            "Starting VLM: model=%s, runtime=%s",
            self.config.model, self.config.runtime,
        )

        try:
            self.runtime = self._create_runtime(self.config.model)
            self.runtime.ensure_running()
            self._started = True
            logger.info("VLM ready: %s via %s", self.config.model, self.config.runtime)

        except Exception as exc:
            logger.warning(
                "Primary VLM failed (%s): %s — trying fallback model '%s'",
                self.config.model, exc, self.config.fallback_model,
            )

            if self.config.fallback_model and self.config.fallback_model != self.config.model:
                try:
                    self.runtime = self._create_runtime(self.config.fallback_model)
                    self.runtime.ensure_running()
                    self._started = True
                    logger.info(
                        "Fallback VLM ready: %s via %s",
                        self.config.fallback_model, self.config.runtime,
                    )
                except Exception as exc2:
                    logger.error("Fallback VLM also failed: %s", exc2)
                    self.runtime = None
                    raise RuntimeError(
                        f"No VLM runtime available. Primary: {exc}, Fallback: {exc2}"
                    )
            else:
                self.runtime = None
                raise RuntimeError(f"VLM startup failed: {exc}")

    def stop(self) -> None:
        """Gracefully shut down the VLM runtime."""
        if self.runtime and hasattr(self.runtime, "stop"):
            try:
                self.runtime.stop()
                logger.info("VLM runtime stopped")
            except Exception as exc:
                logger.warning("Error stopping VLM runtime: %s", exc)
        self.runtime = None
        self._started = False

    def is_available(self) -> bool:
        """Check if a VLM runtime is started and responsive."""
        if not self._started or self.runtime is None:
            return False
        try:
            self.runtime.ensure_running()
            return True
        except Exception:
            return False

    def health_check(self) -> dict[str, str]:
        """Run a health check on the VLM runtime.

        Returns:
            Dict with runtime status information.
        """
        status: dict[str, str] = {
            "vlm_enabled": str(self.config.enabled),
            "vlm_model": self.config.model,
            "vlm_runtime": self.config.runtime,
        }

        if self.runtime:
            try:
                self.runtime.ensure_running()
                status["vlm_status"] = "healthy"
            except Exception as exc:
                status["vlm_status"] = f"unhealthy: {exc}"
        else:
            status["vlm_status"] = "not started"

        return status

    def complete_with_image(self, image_path: str, prompt: str) -> str:
        """Forward an inference request to the active runtime.

        Args:
            image_path: Path to the PNG image.
            prompt:     Text prompt for the VLM.

        Returns:
            Model response text.

        Raises:
            RuntimeError: If no VLM runtime is available.
        """
        if self.runtime is None:
            raise RuntimeError("No VLM runtime available")

        return self.runtime.complete_with_image(
            image_path=image_path,
            prompt=prompt,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        )

    def _create_runtime(self, model: str):
        """Create a runtime instance based on configuration.

        Args:
            model: Model name to use.

        Returns:
            Runtime instance (OllamaRuntime, LlamaCppRuntime, or TransformersRuntime).
        """
        if self.config.runtime == "ollama":
            from docforge.vlm.runtime_ollama import OllamaRuntime
            return OllamaRuntime(
                model=model,
                port=self.config.ollama_port,
                timeout=self.config.timeout_seconds,
            )

        elif self.config.runtime == "llamacpp":
            from docforge.vlm.runtime_llamacpp import LlamaCppRuntime
            runtime = LlamaCppRuntime(
                model_path=self.config.model_path,
                mmproj_path=self.config.mmproj_path,
                port=self.config.llamacpp_port,
                context_length=self.config.context_length,
                threads=self.config.threads,
                gpu_layers=self.config.gpu_layers,
                timeout=self.config.timeout_seconds,
            )
            runtime.start_server()
            return runtime

        elif self.config.runtime == "transformers":
            from docforge.vlm.runtime_transformers import TransformersRuntime
            return TransformersRuntime(hf_model_id=self.config.hf_model_id)

        else:
            raise ValueError(f"Unknown VLM runtime: {self.config.runtime}")
