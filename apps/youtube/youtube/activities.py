from datetime import date, datetime, timezone

from temporalio import activity

from youtube.modules.analytics import blank_metrics, snapshot_plan
from youtube.modules.competitors import pattern_report
from youtube.modules.diagnostician import Funnel, Optimizer, apply_fix, diagnose, review_change
from youtube.modules.gate import QualityGate
from youtube.metadata import apply_metadata_change, push_metadata_change
from youtube.modules.analytics import metrics_from_analytics_api
from youtube.providers_factory import data_client
from youtube.modules.niche import scout
from youtube.modules.packaging import build_variants
from youtube.modules.planner import build_calendar
from youtube.modules.publisher import PublishRequest, publish
from youtube.modules.research import Claim, ResearchBrief, research_topic
from youtube.modules.llm_script import LlmScriptWriter
from youtube.modules.render import ProductionRenderer
from youtube.modules.script import Script
from youtube.modules.thumbnails import save_thumbnails
from youtube.modules.visuals import Asset, build_timeline
from youtube.modules.voice import VoiceStage
from youtube.modules.ypp import ypp_progress
from youtube.pipeline import run_private_dry_run
from youtube.runtime_ctx import youtube_runtime


def _brief_from(payload: dict) -> ResearchBrief:
    return ResearchBrief(
        topic_slug=payload["topic_slug"],
        sources=payload["sources"],
        claims=[Claim(text=item["text"], source_url=item["source_url"]) for item in payload["claims"]],
        provisional=payload.get("provisional", True),
    )


def _brief_to(brief: ResearchBrief) -> dict:
    return {
        "topic_slug": brief.topic_slug,
        "sources": brief.sources,
        "claims": [{"text": claim.text, "source_url": claim.source_url} for claim in brief.claims],
        "provisional": brief.provisional,
    }


def _script_from(payload: dict) -> Script:
    return Script(
        title=payload["title"],
        hook=payload["hook"],
        body=payload["body"],
        ending=payload["ending"],
        short_cutdown=payload["short_cutdown"],
        claims=[Claim(text=item["text"], source_url=item["source_url"]) for item in payload["claims"]],
        format_name=payload["format_name"],
        target_seconds=payload["target_seconds"],
        topic_slug=payload["topic_slug"],
        provisional=payload.get("provisional", True),
    )


def _script_to(script: Script) -> dict:
    return {
        "title": script.title,
        "hook": script.hook,
        "body": script.body,
        "ending": script.ending,
        "short_cutdown": script.short_cutdown,
        "claims": [{"text": claim.text, "source_url": claim.source_url} for claim in script.claims],
        "format_name": script.format_name,
        "target_seconds": script.target_seconds,
        "topic_slug": script.topic_slug,
        "provisional": script.provisional,
    }


@activity.defn
def m2_niche_scout(payload: dict) -> dict:
    choice = scout(payload.get("videos_by_slug"))
    return {"slug": choice.slug, "score": choice.score, "scores": choice.scores}


@activity.defn
def m3_competitor_report(payload: dict) -> dict:
    return pattern_report(payload["videos"])


@activity.defn
def m4_topic_calendar(payload: dict) -> dict:
    calendar = build_calendar(date.fromisoformat(payload["start"]), payload["topics"])
    return {"calendar": calendar}


@activity.defn
def m5_research(payload: dict) -> dict:
    ctx = youtube_runtime()
    if ctx.use_live_research():
        brief = research_topic(payload["slug"], llm=ctx.llm, dry_run=False)
    else:
        brief = research_topic(payload["slug"], dry_run=True)
    return _brief_to(brief)


@activity.defn
def m6_script(payload: dict) -> dict:
    ctx = youtube_runtime()
    script = LlmScriptWriter(llm=ctx.llm).write(
        payload["topic"],
        _brief_from(payload["brief"]),
        previous_format=payload.get("previous_format"),
        rewrite_notes=payload.get("rewrite_notes"),
    )
    return _script_to(script)


@activity.defn
def m7_quality_gate(payload: dict) -> dict:
    return QualityGate().evaluate(
        _script_from(payload["script"]),
        _brief_from(payload["brief"]),
        payload.get("competitor_titles", []),
        payload.get("past_scripts", []),
        payload.get("previous_format"),
    )


@activity.defn
def m8_voice(payload: dict) -> dict:
    ctx = youtube_runtime()
    stage = VoiceStage(tts=ctx.tts)
    track = stage.render(payload["narration"], payload.get("destination", "narration.wav"))
    return {"path": track.path, "synthetic": track.synthetic, "voice_id": track.voice_id, "loudness_target": track.loudness_target}


@activity.defn
def m9_visuals(payload: dict) -> dict:
    assets = [Asset(**item) for item in payload["assets"]]
    timeline = build_timeline(payload["slug"], payload["target_seconds"], assets, shorts=payload.get("shorts", False))
    return {"width": timeline.width, "height": timeline.height, "scenes": len(timeline.scenes), "argv": timeline.argv}


@activity.defn
def m10_packaging(payload: dict) -> dict:
    packaged = build_variants(payload["title"], payload.get("competitor_titles", []))
    slug = payload.get("slug", payload["title"].lower().replace(" ", "-"))
    thumbs = save_thumbnails(slug, packaged["thumbnails"])
    return {
        "titles": packaged["titles"],
        "thumbnails": thumbs,
        "palette": list(packaged["palette"]),
    }


@activity.defn
def m9_render(payload: dict) -> dict:
    ctx = youtube_runtime()
    renderer = ProductionRenderer(storage=ctx.storage, tts=ctx.tts)
    topic = payload["topic"]
    script = payload["script"]
    if topic.get("kind") == "short":
        return renderer.render_short(topic["slug"], script["short_cutdown"], topic.get("target_seconds", 45))
    assets = [Asset(**item) for item in payload.get("assets", [])]
    return renderer.render_long(
        topic["slug"],
        script["hook"] + " " + script["body"],
        payload.get("target_seconds", 120),
        assets,
    )


@activity.defn
def m11_publish(payload: dict) -> dict:
    ctx = youtube_runtime()
    dry_run, provisional = ctx.publish_mode()
    content = payload.get("content", b"dry-run-mp4")
    if payload.get("asset_key"):
        content = ctx.storage.get(payload["asset_key"])
    request = PublishRequest(
        idempotency_key=payload["idempotency_key"],
        title=payload["title"],
        description=payload.get("description", ""),
        tags=payload.get("tags", ["psychology"]),
        category_id="27",
        language="en",
        made_for_kids=False,
        contains_synthetic_media=True,
        uses_ai_voice=payload.get("uses_ai_voice", True),
        uses_realistic_ai_imagery=False,
        privacy_status="private" if dry_run else payload.get("privacy_status", "public"),
        dry_run=dry_run,
        provisional_research=provisional if payload.get("provisional_research") is None else payload["provisional_research"],
        chapters=[{"start": 0, "title": "Hook"}],
        content=payload.get("content", b"dry-run-mp4"),
    )
    row = publish(
        request,
        store=ctx.store,
        client=ctx.client,
        jobs=ctx.jobs,
        ledger=ctx.ledger,
        kill_active=ctx.kill.active("youtube"),
        audit_approved=ctx.audit_approved,
        kind=payload.get("kind", "long"),
    )
    if payload.get("thumbnail_path") and hasattr(ctx.client, "set_thumbnail"):
        try:
            ctx.client.set_thumbnail(row["youtube_id"], open(payload["thumbnail_path"], "rb").read())
        except Exception:
            pass
    return {"youtube_id": row["youtube_id"], "privacy_status": row["privacy_status"], "idempotency_key": row["idempotency_key"]}


@activity.defn
def m12_collect_metrics(payload: dict) -> dict:
    ctx = youtube_runtime()
    video_id = payload["video_id"]
    label = payload["label"]
    metrics = blank_metrics()
    if ctx.analytics is not None:
        try:
            live = ctx.analytics.query_video(video_id, payload["start_date"], payload["end_date"])
            metrics.update(metrics_from_analytics_api(live))
            geo = ctx.analytics.query_geography(video_id, payload["start_date"], payload["end_date"])
            metrics["audienceGeography"] = [
                {"country": row[0], "views": row[1]} for row in geo.get("rows", [])
            ]
        except Exception:
            metrics.update(payload.get("metrics", {}))
    else:
        metrics.update(payload.get("metrics", {}))
    captured_at = datetime.now(timezone.utc).isoformat()
    if ctx.metrics is not None:
        ctx.metrics.save(video_id, label, metrics, captured_at)
    return {"video_id": video_id, "label": label, "metrics": metrics, "captured_at": captured_at}


@activity.defn
def m12_snapshot_plan(payload: dict) -> dict:
    published_at = datetime.fromisoformat(payload["published_at"])
    return {"plan": snapshot_plan(published_at)}


@activity.defn
def m13_diagnose(payload: dict) -> dict:
    return diagnose(Funnel(**payload["funnel"]), [])


@activity.defn
def m13_apply_fix(payload: dict) -> dict:
    ctx = youtube_runtime()
    optimizer = Optimizer()
    funnel = Funnel(**payload["funnel"])
    now = datetime.now(timezone.utc)
    change = apply_fix(optimizer, payload["video_id"], funnel, now, new_value=payload.get("new_value", "next-ranked"))
    client = data_client(ctx.settings, ctx.vault) or ctx.client
    pushed = push_metadata_change(
        client,
        payload["video_id"],
        change.lever,
        payload.get("new_value", "next-ranked"),
        payload.get("current_metadata", {}),
        thumbnail_bytes=payload.get("thumbnail_bytes"),
    )
    updated = pushed["updated"]
    review = review_change(change, now + __import__("datetime").timedelta(hours=73), funnel.ctr)
    stored = None
    if ctx.optimizer is not None:
        stored = ctx.optimizer.record_change(
            payload["video_id"],
            change.lever,
            change.status,
            str(change.baseline),
            {"updated": updated, "review": review, "api": pushed.get("api")},
        )
    return {"change": change.lever, "updated": updated, "review": review, "stored": stored, "api": pushed.get("api")}


@activity.defn
def m14_record_exception(payload: dict) -> dict:
    ctx = youtube_runtime()
    item = ctx.exceptions.add(payload["kind"], payload["message"], scope=payload.get("scope", "youtube"))
    ctx.notifier.alert(f"YouTube exception: {payload['kind']} — {payload['message']}")
    return {"recorded": True, "id": item["id"]}


@activity.defn
def m14_private_dry_run(payload: dict) -> dict:
    report = run_private_dry_run(payload.get("topics"))
    return {"passed": report["passed"], "uploads": report["uploads"]}


@activity.defn
def m4_ypp_progress(payload: dict) -> dict:
    return ypp_progress(payload.get("subscribers", 0), payload.get("watch_hours", 0))


@activity.defn
def m3_discover_competitors(payload: dict) -> dict:
    from youtube.modules.discover import collect_snapshots, discover_channels, persist_channels

    ctx = youtube_runtime()
    channels = discover_channels(ctx.client, payload.get("keywords", ["psychology"]), cap=payload.get("cap", 20))
    saved = persist_channels(ctx.session, channels) if ctx.session is not None else 0
    snapshots = []
    research_client = data_client(ctx.settings, ctx.vault) or ctx.client
    for channel in channels[:5]:
        if hasattr(research_client, "list_channel_videos"):
            video_ids = research_client.list_channel_videos(channel["channel_id"], max_results=10)
        else:
            video_ids = [f"{channel['channel_id']}-v{i}" for i in range(3)]
        snapshots.extend(collect_snapshots(research_client, channel["channel_id"], video_ids, ctx.session))
    return {"channels": len(channels), "saved": saved, "snapshots": len(snapshots)}


YOUTUBE_ACTIVITIES = [
    m2_niche_scout,
    m3_competitor_report,
    m4_topic_calendar,
    m4_ypp_progress,
    m5_research,
    m6_script,
    m7_quality_gate,
    m8_voice,
    m9_visuals,
    m9_render,
    m10_packaging,
    m3_discover_competitors,
    m11_publish,
    m12_collect_metrics,
    m12_snapshot_plan,
    m13_diagnose,
    m13_apply_fix,
    m14_record_exception,
    m14_private_dry_run,
]
