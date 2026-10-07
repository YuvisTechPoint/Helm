from dataclasses import dataclass, field

from core.errors import PublishingBlocked


@dataclass
class Asset:
    key: str
    kind: str
    licence: str
    synthetic: bool = False


@dataclass
class Timeline:
    width: int
    height: int
    scenes: list[dict] = field(default_factory=list)
    argv: list[str] = field(default_factory=list)
    assets: list[Asset] = field(default_factory=list)


def build_timeline(topic_slug: str, target_seconds: int, assets: list[Asset], shorts: bool = False) -> Timeline:
    if target_seconds <= 0:
        raise ValueError("target length must be positive")
    for asset in assets:
        if not asset.licence:
            raise PublishingBlocked(f"asset {asset.key} has no licence")
    width, height = (1080, 1920) if shorts else (1920, 1080)
    scenes = []
    cursor = 0
    index = 0
    while cursor < target_seconds:
        duration = min(30, target_seconds - cursor)
        scenes.append(
            {
                "start": cursor,
                "duration": duration,
                "label": f"{topic_slug} diagram {index + 1}",
            }
        )
        cursor += duration
        index += 1
    filters = []
    if shorts:
        filters.append("subtitles=captions.srt")
    filters.append(f"scale={width}:{height}")
    argv = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=0x1b1f3b:s={width}x{height}:d={target_seconds}",
        "-vf",
        ",".join(filters),
        f"{topic_slug}.mp4",
    ]
    return Timeline(width=width, height=height, scenes=scenes, argv=argv, assets=list(assets))
