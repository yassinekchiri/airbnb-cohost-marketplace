import io

import pytest
from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "teal").save(buf, "PNG")
    return buf.getvalue()


def test_image_field_accepts_real_png():
    f = forms.ImageField().clean(SimpleUploadedFile("a.png", _png(), "image/png"))
    assert f.image.size == (8, 8)  # Pillow decoded it


def test_image_field_rejects_non_image_with_image_extension():
    with pytest.raises(forms.ValidationError):
        forms.ImageField().clean(SimpleUploadedFile("evil.png", b"<?php system($_GET[0]); ?>", "image/png"))
