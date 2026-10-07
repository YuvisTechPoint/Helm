from sqlalchemy import JSON, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


def _empty() -> dict:
    return {}


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), unique=True)
    region: Mapped[str] = mapped_column(String(16))
    kill_switch: Mapped[int] = mapped_column(Integer, default=0)


class ServiceProfileRow(Base):
    __tablename__ = "service_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(Integer)
    body: Mapped[dict] = mapped_column(JSON, default=_empty)
    approved: Mapped[int] = mapped_column(Integer, default=0)


class ICPCellRow(Base):
    __tablename__ = "icp_cells"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(120))
    body: Mapped[dict] = mapped_column(JSON, default=_empty)
    successes: Mapped[int] = mapped_column(Integer, default=0)
    failures: Mapped[int] = mapped_column(Integer, default=0)


class CompanyRow(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    domain: Mapped[str] = mapped_column(String(200))
    body: Mapped[dict] = mapped_column(JSON, default=_empty)


class LeadRow(Base):
    __tablename__ = "leads"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_lead_tenant_email"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    email: Mapped[str] = mapped_column(String(200))
    stage: Mapped[str] = mapped_column(String(32), default="sourced")
    body: Mapped[dict] = mapped_column(JSON, default=_empty)


class ConsentRow(Base):
    __tablename__ = "consents"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    lead_email: Mapped[str] = mapped_column(String(200))
    channel: Mapped[str] = mapped_column(String(32))
    basis: Mapped[str] = mapped_column(String(64))
    withdrawn: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    withdrawn_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class ConversationRow(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    lead_email: Mapped[str] = mapped_column(String(200))
    messages: Mapped[dict] = mapped_column(JSON, default=_empty)
    state: Mapped[str] = mapped_column(String(32), default="open")


class DealRow(Base):
    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    lead_email: Mapped[str] = mapped_column(String(200))
    price_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32))
    body: Mapped[dict] = mapped_column(JSON, default=_empty)


class SuppressionRow(Base):
    __tablename__ = "suppressions"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    value: Mapped[str] = mapped_column(String(200), index=True)
    kind: Mapped[str] = mapped_column(String(32))


class MailboxRow(Base):
    __tablename__ = "mailboxes"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    address: Mapped[str] = mapped_column(String(200), unique=True)
    domain: Mapped[str] = mapped_column(String(200), index=True)
    daily_cap: Mapped[int] = mapped_column(Integer, default=30)
    paused: Mapped[int] = mapped_column(Integer, default=0)


class AcqStateRow(Base):
    """Per-tenant learning state: score weights, experiments, reports."""

    __tablename__ = "acq_state"
    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_acq_state_tenant_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    key: Mapped[str] = mapped_column(String(80))
    body: Mapped[dict] = mapped_column(JSON, default=_empty)


class PromptVersionRow(Base):
    __tablename__ = "prompt_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    active: Mapped[int] = mapped_column(Integer, default=0)
    body: Mapped[str] = mapped_column(Text, default="")
