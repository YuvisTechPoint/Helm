import json
from urllib.parse import urlencode

from core.errors import MissingCredentials

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def authorization_url(client_id: str, redirect_uri: str, state: str) -> str:
    if not client_id:
        raise MissingCredentials("YT_CLIENT_ID")
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(YOUTUBE_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
    )
    return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"


class AnthropicLlm:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5"):
        if not api_key:
            raise MissingCredentials("ANTHROPIC_API_KEY")
        self.api_key = api_key
        self.model = model

    def complete(self, system: str, user: str) -> str:
        import httpx

        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": 2000,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            timeout=90,
        )
        response.raise_for_status()
        return response.json()["content"][0]["text"]


class OpenAiLlm:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        if not api_key:
            raise MissingCredentials("OPENAI_API_KEY")
        self.api_key = api_key
        self.model = model

    def complete(self, system: str, user: str) -> str:
        import httpx

        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "content-type": "application/json"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=90,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


class FailoverLlm:
    def __init__(self, primary, secondary):
        self.primary = primary
        self.secondary = secondary

    def complete(self, system: str, user: str) -> str:
        try:
            return self.primary.complete(system, user)
        except Exception:
            return self.secondary.complete(system, user)


class GoogleYouTubeData:
    def __init__(self, access_token: str):
        if not access_token:
            raise MissingCredentials("YouTube access token")
        self.access_token = access_token

    def search(self, query: str, max_results: int = 10) -> list[dict]:
        import httpx

        response = httpx.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={"part": "snippet", "q": query, "type": "video", "maxResults": max_results},
            headers={"Authorization": f"Bearer {self.access_token}"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("items", [])

    def list_videos(self, video_ids: list[str]) -> list[dict]:
        import httpx

        response = httpx.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={"part": "snippet,statistics,contentDetails", "id": ",".join(video_ids)},
            headers={"Authorization": f"Bearer {self.access_token}"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("items", [])

    def list_channel_videos(self, channel_id: str, max_results: int = 50) -> list[str]:
        import httpx

        response = httpx.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "channelId": channel_id,
                "type": "video",
                "order": "date",
                "maxResults": max_results,
            },
            headers={"Authorization": f"Bearer {self.access_token}"},
            timeout=30,
        )
        response.raise_for_status()
        return [item["id"]["videoId"] for item in response.json().get("items", []) if item.get("id", {}).get("videoId")]

    def update_video(self, video_id: str, snippet: dict | None = None, status: dict | None = None) -> dict:
        import httpx

        body: dict = {"id": video_id}
        parts: list[str] = []
        if snippet:
            body["snippet"] = snippet
            parts.append("snippet")
        if status:
            body["status"] = status
            parts.append("status")
        if not parts:
            return {"video_id": video_id, "updated": False}
        response = httpx.put(
            "https://www.googleapis.com/youtube/v3/videos",
            params={"part": ",".join(parts)},
            headers={"Authorization": f"Bearer {self.access_token}", "content-type": "application/json"},
            json=body,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def set_thumbnail(self, video_id: str, content: bytes) -> dict:
        import httpx

        response = httpx.post(
            "https://www.googleapis.com/upload/youtube/v3/thumbnails/set",
            params={"videoId": video_id},
            headers={"Authorization": f"Bearer {self.access_token}", "content-type": "image/png"},
            content=content,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()


class ResumableUploader:
    """videos.insert resumable session. Transport is an httpx-like client."""

    def __init__(self, transport, access_token: str):
        self.transport = transport
        self.access_token = access_token

    def insert(self, metadata: dict, content: bytes, content_type: str = "video/mp4") -> dict:
        init = self.transport.post(
            "https://www.googleapis.com/upload/youtube/v3/videos",
            params={"uploadType": "resumable", "part": "snippet,status"},
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "X-Upload-Content-Type": content_type,
                "Content-Type": "application/json",
            },
            json=metadata,
        )
        location = init.headers["Location"]
        uploaded = self.transport.put(
            location,
            headers={"Authorization": f"Bearer {self.access_token}", "Content-Type": content_type},
            content=content,
        )
        return uploaded.json()


class YouTubeAnalyticsClient:
    def __init__(self, access_token: str):
        if not access_token:
            raise MissingCredentials("YouTube Analytics token")
        self.access_token = access_token

    def query_video(self, video_id: str, start_date: str, end_date: str) -> dict:
        import httpx

        metrics = ",".join(
            [
                "views",
                "averageViewDuration",
                "likes",
                "subscribersGained",
                "subscribersLost",
                "videoThumbnailImpressions",
                "videoThumbnailImpressionsClickRate",
            ]
        )
        response = httpx.get(
            "https://youtubeanalytics.googleapis.com/v2/reports",
            params={
                "ids": "channel==MINE",
                "startDate": start_date,
                "endDate": end_date,
                "metrics": metrics,
                "filters": f"video=={video_id}",
            },
            headers={"Authorization": f"Bearer {self.access_token}"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def query_geography(self, video_id: str, start_date: str, end_date: str) -> dict:
        import httpx

        response = httpx.get(
            "https://youtubeanalytics.googleapis.com/v2/reports",
            params={
                "ids": "channel==MINE",
                "startDate": start_date,
                "endDate": end_date,
                "metrics": "views",
                "dimensions": "country",
                "filters": f"video=={video_id}",
            },
            headers={"Authorization": f"Bearer {self.access_token}"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()


LICENSED_VOICES = {
    "stock-calm-en-us": {"provider": "elevenlabs", "cloned": False},
    "stock-warm-en-gb": {"provider": "backup", "cloned": False},
}


class ElevenLabsTts:
    def __init__(self, api_key: str, voice_id: str = "stock-calm-en-us"):
        if not api_key:
            raise MissingCredentials("ELEVENLABS_API_KEY")
        self._reject_clone(voice_id)
        self.api_key = api_key
        self.voice_id = voice_id

    @staticmethod
    def _reject_clone(voice_id: str) -> None:
        meta = LICENSED_VOICES.get(voice_id)
        if meta is None or meta["cloned"]:
            raise MissingCredentials(f"voice {voice_id} is not a licensed stock voice")

    def synthesize(self, text: str) -> bytes:
        import httpx

        response = httpx.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}",
            headers={"xi-api-key": self.api_key, "content-type": "application/json"},
            json={"text": text},
            timeout=120,
        )
        response.raise_for_status()
        return response.content


class FailoverTts:
    def __init__(self, primary, secondary):
        self.primary = primary
        self.secondary = secondary

    def synthesize(self, text: str) -> bytes:
        try:
            return self.primary.synthesize(text)
        except Exception:
            return self.secondary.synthesize(text)


class FakeYouTube:
    def __init__(self):
        self.inserts: list[dict] = []
        self.thumbnails: dict[str, bytes] = {}
        self.metadata: dict[str, dict] = {}
        self._seq = 0

    def search(self, query: str, max_results: int = 10) -> list[dict]:
        return [
            {
                "id": {"videoId": f"vid-search-{index}"},
                "snippet": {"channelId": f"chan-{index % 3}", "channelTitle": f"Channel {index}", "title": f"{query} {index}"},
            }
            for index in range(min(max_results, 5))
        ]

    def list_videos(self, video_ids: list[str]) -> list[dict]:
        return [
            {"id": video_id, "snippet": {"title": video_id}, "statistics": {"viewCount": str(1000 + index * 250)}}
            for index, video_id in enumerate(video_ids)
        ]

    def insert(self, metadata: dict, content: bytes) -> dict:
        self._seq += 1
        record = {"id": f"vid{self._seq}", "metadata": metadata, "size": len(content)}
        self.inserts.append(record)
        self.metadata[record["id"]] = dict(metadata)
        return record

    def list_channel_videos(self, channel_id: str, max_results: int = 50) -> list[str]:
        return [f"{channel_id}-v{index}" for index in range(min(max_results, 5))]

    def update_video(self, video_id: str, snippet: dict | None = None, status: dict | None = None) -> dict:
        row = self.metadata.setdefault(video_id, {"snippet": {}, "status": {}})
        if snippet:
            row.setdefault("snippet", {}).update(snippet)
        if status:
            row.setdefault("status", {}).update(status)
        return {"id": video_id, "snippet": row.get("snippet"), "status": row.get("status")}

    def set_thumbnail(self, video_id: str, content: bytes) -> dict:
        self.thumbnails[video_id] = content
        return {"video_id": video_id, "bytes": len(content)}


class FakeTransport:
    def __init__(self, video_id: str = "uploaded1"):
        self.calls: list[tuple[str, str]] = []
        self.video_id = video_id

    def post(self, url, params=None, headers=None, json=None):
        self.calls.append(("POST", url))
        self.last_json = json

        class Response:
            headers = {"Location": "https://uploads.example/session"}

        return Response()

    def put(self, url, headers=None, content=None):
        self.calls.append(("PUT", url))
        body = json.dumps({"id": self.video_id}).encode()

        class Response:
            def json(self_inner):
                return json.loads(body)

        return Response()
