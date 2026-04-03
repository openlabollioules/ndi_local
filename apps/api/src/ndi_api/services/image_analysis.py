"""Image analysis service using vision-capable LLM.

Supports vision-language models via any OpenAI-compatible server (vLLM, etc.)
"""

from __future__ import annotations

import base64
import io
import logging
from dataclasses import dataclass
from pathlib import Path

from langchain_core.messages import HumanMessage
from PIL import Image

from ndi_api.services.llm import get_vision_llm
from ndi_api.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class ImageAnalysisResult:
    """Result of image analysis."""

    description: str
    confidence: float
    objects_detected: list[str]
    text_found: str | None = None
    analysis_type: str = "general"


class ImageAnalysisService:
    """Service for analyzing images using vision-capable LLM."""

    SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
    MAX_DIMENSION = 2048  # Max width/height

    def __init__(self):
        self.llm = None
        self.vision_model_name = settings.vision_model or settings.llm_model
        self._ensure_vision_model()

    def _ensure_vision_model(self):
        """Log a reminder if the configured model may not support vision."""
        current_model = self.vision_model_name.lower()
        # Known vision-capable model families
        vision_hints = [
            "llava",
            "bakllava",
            "moondream",
            "qwen2.5-vl",
            "qwen2-vl",
            "gemma3",
            "granite3.2-vision",
            "gpt-4o",
            "gpt-4-vision",
            "pixtral",
            "internvl",
        ]
        if not any(hint in current_model for hint in vision_hints):
            logger.warning(
                "Model '%s' may not support vision. " "Set NDI_VISION_MODEL to a vision-capable model.",
                current_model,
            )

    def _validate_image(self, image_bytes: bytes, filename: str) -> tuple[bool, str]:
        """Validate image format and size."""
        # Check file size
        if len(image_bytes) > self.MAX_IMAGE_SIZE:
            return (
                False,
                f"Image too large: {len(image_bytes) / 1024 / 1024:.1f}MB > {self.MAX_IMAGE_SIZE / 1024 / 1024}MB",
            )

        # Check extension
        ext = Path(filename).suffix.lower()
        if ext not in self.SUPPORTED_FORMATS:
            return False, f"Unsupported format: {ext}. Use: {self.SUPPORTED_FORMATS}"

        # Try to open with PIL
        try:
            img = Image.open(io.BytesIO(image_bytes))
            img.verify()  # Verify it's a valid image
            return True, ""
        except Exception as e:
            return False, f"Invalid image: {str(e)}"

    def _resize_if_needed(self, image: Image.Image) -> Image.Image:
        """Resize image if dimensions exceed maximum."""
        width, height = image.size

        if width > self.MAX_DIMENSION or height > self.MAX_DIMENSION:
            # Calculate scaling factor
            scale = min(self.MAX_DIMENSION / width, self.MAX_DIMENSION / height)
            new_width = int(width * scale)
            new_height = int(height * scale)

            logger.info(f"Resizing image from {width}x{height} to {new_width}x{new_height}")
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        return image

    def _encode_image(self, image_bytes: bytes) -> str:
        """Encode image to base64 for LLM API."""
        # Open and process image
        img = Image.open(io.BytesIO(image_bytes))

        # Convert to RGB if necessary (handles RGBA, palette, etc.)
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Resize if too large
        img = self._resize_if_needed(img)

        # Save to bytes
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)

        # Encode to base64
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    async def analyze_image(
        self, image_bytes: bytes, filename: str, prompt: str | None = None, analysis_type: str = "general"
    ) -> ImageAnalysisResult:
        """
        Analyze an image using vision-capable LLM.

        Args:
            image_bytes: Raw image bytes
            filename: Original filename
            prompt: Custom prompt for analysis (optional)
            analysis_type: Type of analysis (general, ocr, objects, chart)

        Returns:
            ImageAnalysisResult with description and metadata
        """
        # Validate
        is_valid, error_msg = self._validate_image(image_bytes, filename)
        if not is_valid:
            raise ValueError(error_msg)

        # Encode image
        base64_image = self._encode_image(image_bytes)

        # Select prompt based on analysis type
        if not prompt:
            prompt = self._get_prompt_for_type(analysis_type)

        # Build multimodal HumanMessage (OpenAI-compatible vision)
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                },
            ]
        )

        # Call LLM
        try:
            if self.llm is None:
                self.llm = get_vision_llm()

            from ndi_api.services.llm import strip_thinking

            response = await self.llm.ainvoke([message])
            description = strip_thinking(str(response.content if hasattr(response, "content") else response))

            # Extract objects (simple heuristic)
            objects_detected = self._extract_objects(description)

            return ImageAnalysisResult(
                description=description,
                confidence=0.85,  # Could be refined
                objects_detected=objects_detected,
                analysis_type=analysis_type,
            )

        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            raise RuntimeError(f"Failed to analyze image: {str(e)}")

    def _get_prompt_for_type(self, analysis_type: str) -> str:
        """Get appropriate prompt for analysis type."""
        prompts = {
            "general": (
                "Décrivez cette image en détail. Incluez:\n"
                "- Le contenu principal\n"
                "- Les objets présents\n"
                "- Le contexte ou la scène\n"
                "- Les couleurs dominantes\n"
                "- Tout texte visible\n\n"
                "Répondez en français."
            ),
            "ocr": (
                "Extraire tout le texte visible dans cette image. "
                "Présentez-le de manière structurée. "
                "Si c'est un document, préservez la mise en forme."
            ),
            "objects": (
                "Listez tous les objets identifiables dans cette image. "
                "Pour chaque objet, indiquez:\n"
                "- Le nom de l'objet\n"
                "- Sa position approximative\n"
                "- Sa taille relative\n\n"
                "Format: liste à puces."
            ),
            "chart": (
                "Analysez ce graphique ou tableau de données. Décrivez:\n"
                "- Le type de visualisation\n"
                "- Les axes et leurs unités\n"
                "- Les tendances principales\n"
                "- Les valeurs remarquables\n\n"
                "Répondez en français."
            ),
            "data_table": (
                "Cette image contient un tableau de données. "
                "Extrayez les données sous forme de tableau markdown. "
                "Préservez les en-têtes et les valeurs exactes."
            ),
        }
        return prompts.get(analysis_type, prompts["general"])

    def _extract_objects(self, description: str) -> list[str]:
        """Extract mentioned objects from description (simple heuristic)."""
        # Common object indicators
        indicators = ["contient", "présente", "montre", "on voit", "il y a", "objet", "objets", "élément", "éléments"]

        objects = []
        lines = description.lower().split("\n")

        for line in lines:
            for indicator in indicators:
                if indicator in line:
                    # Extract potential object (simplistic)
                    parts = line.split(indicator)
                    if len(parts) > 1:
                        obj = parts[1].strip().rstrip(".,;").split()[0:3]
                        if obj:
                            objects.append(" ".join(obj))

        # Remove duplicates and limit
        seen = set()
        unique_objects = []
        for obj in objects:
            if obj not in seen and len(unique_objects) < 10:
                seen.add(obj)
                unique_objects.append(obj)

        return unique_objects


# Singleton instance
_image_service: ImageAnalysisService | None = None


def get_image_analysis_service() -> ImageAnalysisService:
    """Get or create the image analysis service singleton."""
    global _image_service
    if _image_service is None:
        _image_service = ImageAnalysisService()
    return _image_service
