from pathlib import Path

from core.render import burn_captions, mux_audio_video, run_ffmpeg
from core.storage import MemoryObjectStore
from youtube.modules.visuals import Asset, build_timeline
from youtube.modules.voice import VoiceStage


class ProductionRenderer:
    def __init__(self, workdir: str = "artifacts", storage=None, tts=None):
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.storage = storage or MemoryObjectStore()
        self.voice = VoiceStage(tts=tts)

    def render_long(self, topic_slug: str, narration: str, target_seconds: int, assets: list[Asset]) -> dict:
        audio = self.voice.render(narration, str(self.workdir / f"{topic_slug}.wav"))
        audio_path = self.workdir / f"{topic_slug}.wav"
        audio_path.write_bytes(audio.data)
        timeline = build_timeline(topic_slug, target_seconds, assets, shorts=False)
        video_path = run_ffmpeg(timeline.argv)
        final = mux_audio_video(video_path, audio_path, self.workdir / f"{topic_slug}.mp4")
        key = f"videos/{topic_slug}.mp4"
        payload = final.read_bytes()
        self.storage.put(key, payload)
        return {"key": key, "bytes": len(payload), "path": str(final), "scenes": len(timeline.scenes)}

    def render_short(self, topic_slug: str, narration: str, target_seconds: int) -> dict:
        assets = [Asset(key=f"{topic_slug}-short", kind="diagram", licence="original", synthetic=False)]
        timeline = build_timeline(topic_slug, target_seconds, assets, shorts=True)
        video_path = run_ffmpeg(timeline.argv)
        srt = self.workdir / f"{topic_slug}.srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:30,000\n" + narration[:120], encoding="utf-8")
        captioned = burn_captions(video_path, srt, self.workdir / f"{topic_slug}-short.mp4")
        key = f"shorts/{topic_slug}.mp4"
        payload = captioned.read_bytes()
        self.storage.put(key, payload)
        return {"key": key, "bytes": len(payload), "path": str(captioned)}
