import shutil
import subprocess
from pathlib import Path


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def run_ffmpeg(argv: list[str], *, cwd: str | None = None) -> Path:
    output = Path(argv[-1])
    if not ffmpeg_available():
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"DRY-RUN-VIDEO")
        return output
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or "ffmpeg failed")
    return output


def mux_audio_video(video_path: Path, audio_path: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not ffmpeg_available():
        output_path.write_bytes(video_path.read_bytes() if video_path.exists() else b"DRY-RUN-MP4")
        return output_path
    argv = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-shortest",
        str(output_path),
    ]
    return run_ffmpeg(argv)


def burn_captions(video_path: Path, srt_path: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not ffmpeg_available():
        output_path.write_bytes(video_path.read_bytes() if video_path.exists() else b"DRY-RUN-SHORT")
        return output_path
    argv = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"subtitles={srt_path.as_posix()}",
        "-c:a",
        "copy",
        str(output_path),
    ]
    return run_ffmpeg(argv)
