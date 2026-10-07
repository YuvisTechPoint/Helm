import io
from pathlib import Path

from core.paths import ARTIFACTS_DIR
from youtube.modules.packaging import PALETTE


def render_thumbnail(text: str, palette: tuple[str, ...] = PALETTE, size: tuple[int, int] = (1280, 720)) -> bytes:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return f"THUMB:{text}".encode()

    bg = palette[0].lstrip("#")
    accent = palette[1].lstrip("#")
    image = Image.new("RGB", size, color=f"#{bg}")
    draw = ImageDraw.Draw(image)
    draw.rectangle([(40, 40), (size[0] - 40, size[1] - 40)], outline=f"#{accent}", width=8)
    font = ImageFont.load_default()
    wrapped = text[:48]
    draw.text((80, size[1] // 2 - 20), wrapped, fill=f"#{palette[2].lstrip('#')}", font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def save_thumbnails(topic_slug: str, variants: list[dict], outdir: str | None = None) -> list[dict]:
    outdir = outdir or str(ARTIFACTS_DIR / "thumbnails")
    folder = Path(outdir)
    folder.mkdir(parents=True, exist_ok=True)
    saved = []
    for index, variant in enumerate(variants):
        text = variant.get("text") or variant.get("title", topic_slug)
        data = render_thumbnail(text)
        path = folder / f"{topic_slug}-{index}.png"
        path.write_bytes(data)
        saved.append({**variant, "path": str(path), "bytes": len(data)})
    return saved
