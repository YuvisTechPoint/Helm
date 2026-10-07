from dataclasses import dataclass

from core.errors import MissingCredentials
from youtube.providers import LICENSED_VOICES

LOUDNORM = "loudnorm=I=-14:TP=-1.5:LRA=11"


def assert_licensed_voice(voice_id: str) -> None:
    meta = LICENSED_VOICES.get(voice_id)
    if meta is None or meta["cloned"]:
        raise MissingCredentials("refusing cloned or unlicensed voices")


def loudnorm_argv(source: str, destination: str) -> list[str]:
    return ["ffmpeg", "-y", "-i", source, "-af", LOUDNORM, destination]


@dataclass
class AudioTrack:
    voice_id: str
    path: str
    data: bytes
    loudness_target: str = "-14 LUFS"
    synthetic: bool = True
    ffmpeg_argv: list[str] | None = None


class VoiceStage:
    def __init__(self, tts=None, voice_id: str = "stock-calm-en-us"):
        assert_licensed_voice(voice_id)
        self.tts = tts
        self.voice_id = voice_id

    def render(self, narration: str, destination: str) -> AudioTrack:
        if self.tts is None:
            payload = f"DRY-RUN AUDIO {self.voice_id}\n{narration}".encode()
        else:
            payload = self.tts.synthesize(narration)
        normalized = destination.replace(".wav", ".norm.wav")
        return AudioTrack(
            voice_id=self.voice_id,
            path=normalized,
            data=payload,
            synthetic=True,
            ffmpeg_argv=loudnorm_argv(destination, normalized),
        )
