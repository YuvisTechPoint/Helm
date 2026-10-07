from dataclasses import dataclass

from core.errors import PublishingBlocked
from core.jobs import JobBook
from youtube.modules.planner import assert_cadence
from youtube.quota import QuotaLedger


@dataclass
class PublishRequest:
    idempotency_key: str
    title: str
    description: str
    tags: list[str]
    category_id: str
    language: str
    made_for_kids: bool | None
    contains_synthetic_media: bool | None
    uses_ai_voice: bool
    uses_realistic_ai_imagery: bool
    privacy_status: str
    dry_run: bool
    provisional_research: bool
    chapters: list[dict]
    playlist_id: str | None = None
    scheduled_at: str | None = None
    content: bytes = b"dry-run"


class InMemoryVideoStore:
    def __init__(self):
        self.rows: dict[str, dict] = {}

    def get_by_key(self, key: str) -> dict | None:
        return self.rows.get(key)

    def save(self, row: dict) -> dict:
        self.rows[row["idempotency_key"]] = row
        return row

    def list_all(self) -> list[dict]:
        return list(self.rows.values())


def resolve_privacy(requested: str, audit_approved: bool, dry_run: bool) -> str:
    if requested not in {"private", "unlisted", "public"}:
        raise PublishingBlocked("privacyStatus must be private, unlisted, or public")
    if not audit_approved:
        if not (dry_run and requested == "private"):
            raise PublishingBlocked("audit unconfirmed; refusing insert")
        return "private"
    return requested


def build_metadata(request: PublishRequest, privacy: str) -> dict:
    if request.made_for_kids is None:
        raise PublishingBlocked("madeForKids must be set explicitly")
    synthetic = request.uses_ai_voice or request.uses_realistic_ai_imagery
    if synthetic and not request.contains_synthetic_media:
        raise PublishingBlocked("containsSyntheticMedia is required for AI voice or realistic AI imagery")
    if request.provisional_research and not request.dry_run:
        raise PublishingBlocked("provisional research cannot be published")
    return {
        "snippet": {
            "title": request.title,
            "description": request.description,
            "tags": request.tags,
            "categoryId": request.category_id,
            "defaultLanguage": request.language,
        },
        "status": {
            "privacyStatus": privacy,
            "madeForKids": request.made_for_kids,
            "containsSyntheticMedia": bool(request.contains_synthetic_media),
            "selfDeclaredMadeForKids": request.made_for_kids,
            "publishAt": request.scheduled_at,
        },
        "chapters": request.chapters,
        "playlistId": request.playlist_id,
    }


def publish(
    request: PublishRequest,
    *,
    store: InMemoryVideoStore,
    client,
    jobs: JobBook,
    ledger: QuotaLedger,
    kill_active: bool,
    audit_approved: bool,
    week_counts: dict | None = None,
    kind: str = "long",
) -> dict:
    if kill_active:
        raise PublishingBlocked("kill switch is active")
    if week_counts is not None:
        assert_cadence(week_counts, kind)
    existing_job, created = jobs.begin(request.idempotency_key, "youtube.upload", {"title": request.title})
    if not created and existing_job.get("result"):
        return existing_job["result"]
    stored = store.get_by_key(request.idempotency_key)
    if stored is not None:
        jobs.succeed(request.idempotency_key, stored)
        return stored
    privacy = resolve_privacy(request.privacy_status, audit_approved, request.dry_run)
    metadata = build_metadata(request, privacy)
    ledger.consume_upload()
    uploaded = client.insert(metadata, request.content)
    row = {
        "idempotency_key": request.idempotency_key,
        "youtube_id": uploaded["id"],
        "privacy_status": privacy,
        "title": request.title,
        "metadata": metadata,
        "kind": kind,
        "bytes": len(request.content),
    }
    store.save(row)
    jobs.succeed(request.idempotency_key, row)
    return row
