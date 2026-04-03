"""Tests for image analysis service."""

import io
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ndi_api.services.image_analysis import ImageAnalysisService


def test_image_service_validation():
    """Test image validation in the service."""
    service = ImageAnalysisService()

    # Test invalid format
    is_valid, error = service._validate_image(b"not an image", "test.txt")
    assert not is_valid
    assert "txt" in error or "format" in error.lower()

    # Test valid format but invalid image
    is_valid, error = service._validate_image(b"not an image", "test.jpg")
    assert not is_valid
    assert "invalid" in error.lower()


def test_image_service_supported_formats():
    """Test supported formats configuration."""
    service = ImageAnalysisService()

    assert ".jpg" in service.SUPPORTED_FORMATS
    assert ".jpeg" in service.SUPPORTED_FORMATS
    assert ".png" in service.SUPPORTED_FORMATS
    assert ".gif" in service.SUPPORTED_FORMATS
    assert ".webp" in service.SUPPORTED_FORMATS
    assert ".bmp" in service.SUPPORTED_FORMATS


def test_prompts_for_types():
    """Test that prompts are defined for all analysis types."""
    service = ImageAnalysisService()

    types = ["general", "ocr", "objects", "chart", "data_table"]
    for analysis_type in types:
        prompt = service._get_prompt_for_type(analysis_type)
        assert prompt is not None
        assert len(prompt) > 0

    # Test default fallback
    default_prompt = service._get_prompt_for_type("unknown_type")
    assert default_prompt == service._get_prompt_for_type("general")


def test_image_encoding():
    """Test image encoding to base64."""
    from PIL import Image

    service = ImageAnalysisService()

    # Create a simple test image
    img = Image.new("RGB", (100, 100), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    # Test encoding
    encoded = service._encode_image(img_bytes.getvalue())
    assert encoded is not None
    assert len(encoded) > 0
    # Should be valid base64
    import base64

    decoded = base64.b64decode(encoded)
    assert len(decoded) > 0


def test_object_extraction():
    """Test object extraction from description."""
    service = ImageAnalysisService()

    description = "L'image contient un bateau. On voit aussi une voiture."
    objects = service._extract_objects(description)

    assert isinstance(objects, list)
    # Should extract some keywords
    assert len(objects) > 0
