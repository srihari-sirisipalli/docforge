"""
DocForge — HuggingFace Transformers VLM Runtime
=================================================

Loads a Vision-Language Model directly via HuggingFace Transformers.
Best performance on systems with a GPU (CUDA). Falls back to CPU
with float32 precision.

Requires:
  pip install torch transformers
"""

from __future__ import annotations

from docforge.infra.logging import get_logger

logger = get_logger(__name__)


class TransformersRuntime:
    """VLM runtime using HuggingFace Transformers for direct model loading.

    Provides the best throughput on GPU systems but requires more setup
    and significantly more RAM than quantised GGUF models.
    """

    def __init__(self, hf_model_id: str):
        """Load the model and processor.

        Args:
            hf_model_id: HuggingFace model identifier
                         (e.g., "Qwen/Qwen2-VL-7B-Instruct").
        """
        self.model_id = hf_model_id
        self.model = None
        self.processor = None
        self.device = "cpu"

        self._load_model()

    def _load_model(self) -> None:
        """Load model and processor from HuggingFace."""
        try:
            import torch
            from transformers import AutoModelForVision2Seq, AutoProcessor

            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            dtype = torch.float16 if self.device == "cuda" else torch.float32

            logger.info(
                "Loading Transformers model: %s (device=%s, dtype=%s)",
                self.model_id, self.device, dtype,
            )

            self.processor = AutoProcessor.from_pretrained(
                self.model_id, trust_remote_code=True,
            )
            self.model = AutoModelForVision2Seq.from_pretrained(
                self.model_id,
                torch_dtype=dtype,
                device_map="auto" if self.device == "cuda" else None,
                trust_remote_code=True,
            )

            logger.info("Model loaded successfully: %s", self.model_id)

        except ImportError:
            raise ImportError(
                "Transformers runtime requires: pip install torch transformers\n"
                "For GPU support: pip install torch --index-url "
                "https://download.pytorch.org/whl/cu121"
            )

    def complete_with_image(
        self,
        image_path: str,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> str:
        """Run inference with image + prompt.

        Args:
            image_path:  Path to PNG image.
            prompt:      Text prompt.
            max_tokens:  Max new tokens to generate.
            temperature: Sampling temperature.

        Returns:
            Model response text.
        """
        import torch
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        inputs = self.processor(
            text=prompt, images=image, return_tensors="pt",
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=temperature > 0,
            )

        return self.processor.decode(outputs[0], skip_special_tokens=True)

    def ensure_running(self) -> None:
        """Verify the model is loaded."""
        if self.model is None or self.processor is None:
            raise RuntimeError("Transformers model not loaded")

    def stop(self) -> None:
        """Unload model to free memory."""
        import gc

        self.model = None
        self.processor = None
        gc.collect()

        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

        logger.info("Transformers model unloaded")
