from sqlalchemy import JSON, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


def _empty() -> dict:
    return {}


class NicheRun(Base):
    __tablename__ = "niche_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    chosen_slug: Mapped[str] = mapped_column(String(80))
    scores: Mapped[dict] = mapped_column(JSON, default=_empty)
    ran_at: Mapped[str] = mapped_column(String(40))


class TrackedChannel(Base):
    __tablename__ = "tracked_channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    subscriber_count: Mapped[int] = mapped_column(Integer, default=0)


class VideoSnapshot(Base):
    __tablename__ = "video_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[str] = mapped_column(String(64), index=True)
    channel_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(Text)
    age_label: Mapped[str] = mapped_column(String(16))
    views: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict] = mapped_column(JSON, default=_empty)


class TopicRow(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    title: Mapped[str] = mapped_column(Text)
    cluster: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(32), default="backlog")
    score: Mapped[int] = mapped_column(Integer, default=0)
    planned_on: Mapped[str | None] = mapped_column(String(40), nullable=True)


class PublishedVideo(Base):
    __tablename__ = "published_videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    youtube_id: Mapped[str] = mapped_column(String(64))
    privacy_status: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(Text)
    contains_synthetic_media: Mapped[int] = mapped_column(Integer, default=0)
    made_for_kids: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict] = mapped_column(JSON, default=_empty)


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"
    __table_args__ = (UniqueConstraint("video_id", "label", name="uq_metric_video_label"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str] = mapped_column(String(16))
    metrics: Mapped[dict] = mapped_column(JSON, default=_empty)
    captured_at: Mapped[str] = mapped_column(String(40))


class OptimizationChange(Base):
    __tablename__ = "optimization_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[str] = mapped_column(String(64), index=True)
    lever: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(32))
    baseline: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON, default=_empty)


class PivotProposal(Base):
    __tablename__ = "pivot_proposals"

    id: Mapped[int] = mapped_column(primary_key=True)
    from_slug: Mapped[str] = mapped_column(String(80))
    to_slug: Mapped[str] = mapped_column(String(80))
    proposed_at: Mapped[str] = mapped_column(String(40))
    veto_until: Mapped[str] = mapped_column(String(40))
    vetoed: Mapped[int] = mapped_column(Integer, default=0)
    executed: Mapped[int] = mapped_column(Integer, default=0)
