"""Render a faint, printable watermark shared by PDF and Word exports."""
from io import BytesIO
from pathlib import Path

from matplotlib import get_data_path
from PIL import Image, ImageDraw, ImageFont


def watermark_image(text):
    font_path = Path(get_data_path()) / "fonts" / "ttf" / "DejaVuSans-Bold.ttf"
    font = ImageFont.truetype(font_path, 136)
    left, top, right, bottom = font.getbbox(text)
    image = Image.new("RGBA", (right - left + 16, bottom - top + 16))
    ImageDraw.Draw(image).text((8 - left, 8 - top), text, font=font, fill=(70, 78, 92, 32))
    image.thumbnail((1480, 176), Image.Resampling.LANCZOS)
    image = image.rotate(32, resample=Image.Resampling.BICUBIC, expand=True)
    payload = BytesIO()
    image.save(payload, "PNG")
    return payload.getvalue(), image.width / 4, image.height / 4
