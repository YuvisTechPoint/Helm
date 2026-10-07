from datetime import date

from core.errors import PublishingBlocked
from core.jobs import ExceptionQueue
from core.storage import MemoryObjectStore
from youtube.modules.gate import QualityGate
from youtube.modules.llm_script import LlmScriptWriter
from youtube.modules.packaging import build_variants
from youtube.modules.publisher import InMemoryVideoStore, PublishRequest, publish
from youtube.modules.render import ProductionRenderer
from youtube.modules.research import research_topic
from youtube.modules.thumbnails import save_thumbnails
from youtube.modules.voice import VoiceStage
from youtube.quota import UPLOAD_UNITS, QuotaLedger

DRY_RUN_TOPICS = [
    {"slug": slug, "title": title, "cluster": "psychology", "kind": "long", "demand": 4, "gap": 4, "fit": 5, "target_seconds": 120}
    for slug, title in [
        ("projection", "psychological projection"),
        ("confirmation-bias", "confirmation bias"),
        ("loss-aversion", "loss aversion"),
        ("shadow-work", "Jungian shadow work"),
        ("attachment-styles", "attachment styles"),
        ("cognitive-dissonance", "cognitive dissonance"),
        ("habit-loops", "habit loops"),
        ("social-proof", "social proof"),
        ("scarcity-mindset", "scarcity mindset"),
        ("emotional-regulation", "emotional regulation"),
    ]
]

SHORT_TOPICS = [
    {"slug": f"{row['slug']}-short", "title": row["title"], "cluster": "psychology", "kind": "short", "demand": 4, "gap": 4, "fit": 5, "target_seconds": 45}
    for row in DRY_RUN_TOPICS[:5]
]


def produce_topic(
    topic: dict,
    *,
    writer: LlmScriptWriter | None = None,
    gate: QualityGate,
    store: InMemoryVideoStore,
    client,
    jobs,
    ledger: QuotaLedger,
    queue: ExceptionQueue,
    past_scripts: list[str],
    previous_format: str | None,
    kill_active: bool = False,
    audit_approved: bool = False,
    competitor_titles: list[str] | None = None,
    llm=None,
    tts=None,
    storage=None,
) -> dict:
    competitor_titles = competitor_titles or ["scary stories compilation volume twelve"]
    writer = writer or LlmScriptWriter(llm=llm)
    storage = storage or MemoryObjectStore()
    renderer = ProductionRenderer(storage=storage, tts=tts)
    brief = research_topic(topic["slug"].replace("-short", ""), llm=llm, dry_run=llm is None)
    script = writer.write(topic, brief, previous_format=previous_format)
    decision = None
    for attempt in range(3):
        decision = gate.evaluate(script, brief, competitor_titles, past_scripts, previous_format)
        if decision["decision"] == "pass":
            break
        if decision["decision"] == "reject" or attempt == 2:
            return {"status": "dropped", "slug": topic["slug"], "gate": decision, "rewrites": attempt}
        script = writer.write(topic, brief, previous_format=previous_format, rewrite_notes=decision["reasons"])
    packaging = build_variants(script.title, competitor_titles)
    thumbnails = save_thumbnails(topic["slug"], packaging["thumbnails"])
    narration = script.hook + " " + script.body
    voice = VoiceStage(tts=tts).render(narration, f"{topic['slug']}.wav")
    if topic.get("kind") == "short":
        rendered = renderer.render_short(topic["slug"], script.short_cutdown, topic.get("target_seconds", 45))
        kind = "short"
    else:
        from youtube.modules.visuals import Asset

        assets = [Asset(key=f"{topic['slug']}-diagram", kind="diagram", licence="original", synthetic=False)]
        rendered = renderer.render_long(topic["slug"], narration, max(30, script.target_seconds // 4), assets)
        kind = "long"
    description = script.ending + "\n\nSources:\n" + "\n".join(source["url"] for source in brief.sources)
    content = storage.get(rendered["key"])
    request = PublishRequest(
        idempotency_key=f"dry-{topic['slug']}",
        title=packaging["titles"][0]["title"],
        description=description,
        tags=[topic["cluster"], topic["slug"]],
        category_id="27",
        language="en",
        made_for_kids=False,
        contains_synthetic_media=True,
        uses_ai_voice=voice.synthetic,
        uses_realistic_ai_imagery=False,
        privacy_status="private",
        dry_run=True,
        provisional_research=brief.provisional,
        chapters=[{"start": 0, "title": "Hook"}],
        content=content,
    )
    try:
        published = publish(
            request,
            store=store,
            client=client,
            jobs=jobs,
            ledger=ledger,
            kill_active=kill_active,
            audit_approved=audit_approved,
            kind=kind,
        )
        if hasattr(client, "set_thumbnail") and thumbnails:
            try:
                thumb_bytes = open(thumbnails[0]["path"], "rb").read()
                client.set_thumbnail(published["youtube_id"], thumb_bytes)
            except Exception:
                pass
    except PublishingBlocked as exc:
        queue.add("publish_blocked", str(exc))
        return {"status": "blocked", "slug": topic["slug"], "error": str(exc)}
    return {
        "status": "published_private",
        "slug": topic["slug"],
        "kind": kind,
        "youtube_id": published["youtube_id"],
        "script_text": script.full_text(),
        "format_name": script.format_name,
        "scenes": rendered.get("scenes", 0),
        "bytes": rendered["bytes"],
        "thumbnails": len(thumbnails),
        "gate": decision,
    }


def run_private_dry_run(topics: list[dict] | None = None, include_shorts: bool = True) -> dict:
    topics = list(topics or DRY_RUN_TOPICS)
    if include_shorts:
        topics.extend(SHORT_TOPICS[:2])
    writer = LlmScriptWriter()
    gate = QualityGate()
    store = InMemoryVideoStore()
    from youtube.providers import FakeYouTube

    client = FakeYouTube()
    jobs = __import__("core.jobs", fromlist=["JobBook"]).JobBook()
    ledger = QuotaLedger(daily_limit=max(10_000, len(topics) * UPLOAD_UNITS))
    ledger.reserve_for_scheduled_uploads(len(topics))
    queue = ExceptionQueue()
    past: list[str] = []
    previous_format = None
    results = []
    for topic in topics:
        outcome = produce_topic(
            topic,
            writer=writer,
            gate=gate,
            store=store,
            client=client,
            jobs=jobs,
            ledger=ledger,
            queue=queue,
            past_scripts=past,
            previous_format=previous_format,
        )
        results.append(outcome)
        if outcome["status"] == "published_private":
            past.append(outcome["script_text"])
            previous_format = outcome["format_name"]
    passed = sum(1 for row in results if row["status"] == "published_private")
    return {"passed": passed, "results": results, "uploads": len(client.inserts), "calendar_anchor": date.today().isoformat()}
