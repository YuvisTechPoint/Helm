"""M4 — per-lead research brief with sourced facts."""

from dataclasses import dataclass, field


@dataclass
class ResearchBrief:
    lead_email: str
    company: str
    summary: str
    facts: list[dict] = field(default_factory=list)
    provisional: bool = True

    def as_text(self) -> str:
        lines = [self.summary]
        for fact in self.facts:
            lines.append(f"{fact['text']} (source: {fact['source_url']})")
        return " ".join(lines)


def build_research_brief(lead: dict, profile: dict, llm=None) -> ResearchBrief:
    company = lead.get("company", "the company")
    domain = lead.get("domain", "")
    reason = lead.get("reason", profile["services"][0] if profile.get("services") else "conversion")
    facts = [
        {
            "text": f"{company} operates in {lead.get('industry', profile.get('industry', 'ecommerce'))}.",
            "source_url": f"https://{domain}" if domain else "profile://services",
        },
        {
            "text": reason,
            "source_url": lead.get("trigger_source", "profile://proof_points"),
        },
    ]
    if lead.get("employee_count"):
        facts.append(
            {
                "text": f"Estimated team size: {lead['employee_count']}.",
                "source_url": lead.get("enrichment_source", "apollo://match"),
            }
        )
    summary = f"{company}: {reason}"
    if llm is not None:
        try:
            import json

            raw = llm.complete(
                "Return JSON {summary, facts:[{text, source_url}]}. Only cite provided inputs.",
                json.dumps({"lead": lead, "profile": {"services": profile.get("services"), "proof_points": profile.get("proof_points")}}),
            )
            data = json.loads(raw)
            summary = data.get("summary", summary)
            facts = data.get("facts", facts)
        except Exception:
            pass
    return ResearchBrief(lead_email=lead.get("email", ""), company=company, summary=summary, facts=facts, provisional=not domain)
