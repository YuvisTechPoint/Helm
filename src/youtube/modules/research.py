from dataclasses import dataclass


@dataclass
class Claim:
    text: str
    source_url: str


@dataclass
class ResearchBrief:
    topic_slug: str
    sources: list[dict]
    claims: list[Claim]
    provisional: bool = False

    def source_urls(self) -> set[str]:
        return {source["url"] for source in self.sources}


def provisional_brief(topic_slug: str) -> ResearchBrief:
    sources = [
        {"title": f"Dry-run source {index} for {topic_slug}", "url": f"https://example.org/dry-run/{topic_slug}/{index}"}
        for index in range(1, 6)
    ]
    claims = [Claim(text=f"Dry-run claim {index} about {topic_slug}", source_url=sources[index - 1]["url"]) for index in range(1, 6)]
    return ResearchBrief(topic_slug=topic_slug, sources=sources, claims=claims, provisional=True)


def ensure_sourced(brief: ResearchBrief) -> None:
    if len(brief.sources) < 5:
        raise ValueError("a video needs at least 5 sources")
    urls = brief.source_urls()
    for claim in brief.claims:
        if claim.source_url not in urls:
            raise ValueError(f"unsourced claim: {claim.text}")


def research_topic(topic_slug: str, llm=None, dry_run: bool = False) -> ResearchBrief:
    if llm is not None:
        raw = llm.complete(
            "Return JSON with sources and claims. Every claim needs a source URL from the sources list.",
            topic_slug,
        )
        brief = _parse_llm_brief(topic_slug, raw)
        ensure_sourced(brief)
        return brief
    if not dry_run:
        raise ValueError("live research requires an LLM provider")
    brief = provisional_brief(topic_slug)
    ensure_sourced(brief)
    return brief


def _parse_llm_brief(topic_slug: str, raw: str) -> ResearchBrief:
    import json

    data = json.loads(raw)
    sources = data["sources"]
    claims = [Claim(text=item["text"], source_url=item["source_url"]) for item in data["claims"]]
    return ResearchBrief(topic_slug=topic_slug, sources=sources, claims=claims, provisional=False)


@dataclass
class Script:
    title: str
    hook: str
    body: str
    ending: str
    short_cutdown: str
    claims: list[Claim]
    format_name: str
    target_seconds: int
    topic_slug: str
    provisional: bool = False

    def full_text(self) -> str:
        return "\n".join([self.title, self.hook, self.body, self.ending, self.short_cutdown])


FORMATS = ["essay", "case_study", "myth_bust", "diagram_explainer"]


def next_format(previous: str | None) -> str:
    if previous is None:
        return FORMATS[0]
    index = FORMATS.index(previous)
    return FORMATS[(index + 1) % len(FORMATS)]


TOPIC_LEXICON = {
    "projection": "mirror blame deflect attribute unconscious transfer scapegoat disown reject accuse externalize fantasy",
    "confirmation-bias": "selective cherry evidence seek disconfirm filter partisan prior belief tunnel interpret favor",
    "loss-aversion": "prospect kahneman tversky endowment downside sting gamble framing certainty effect reference point",
    "shadow-work": "jung archetype persona anima animus integration dream symbol gold repressed inferior function",
    "attachment-styles": "bowlby ainsworth secure anxious avoidant disorganized caregiver proximity protest reunion base",
    "cognitive-dissonance": "festinger inconsistency rationalize attitude change effort justification belief revision tension",
    "habit-loops": "cue routine reward craving basal ganglia automaticity implementation intention friction environment design",
    "social-proof": "asch conformity crowd testimonial norm pluralistic ignorance bandwagon authority neighbor signal",
    "scarcity-mindset": "mullainathan shafir bandwidth tunnel tax deadline limited attention poverty cognition tradeoff",
    "emotional-regulation": "gross reappraisal suppression affect labeling window tolerance interoception prefrontal vagal",
}


class ScriptWriter:
    def write(self, topic: dict, brief: ResearchBrief, previous_format: str | None = None, rewrite_notes: list[str] | None = None) -> Script:
        slug = topic["slug"]
        title_name = topic.get("title", slug.replace("-", " "))
        if rewrite_notes:
            title_name = f"A closer look at {title_name}"
        lexicon = TOPIC_LEXICON.get(slug, slug.replace("-", " "))
        hook = (
            f"In the next minute, {title_name} will show the mechanism, the evidence, and the practical payoff. "
            f"This opening names {title_name} before anything else."
        )
        claim_lines = " ".join(f"{claim.text} Source: {claim.source_url}." for claim in brief.claims)
        body = f"{title_name} lexicon: {lexicon}. {claim_lines}"
        ending = (
            f"The payoff of {title_name} is a single habit you can test this week, tied back to the promise in the title "
            f"and the {slug} lexicon words above."
        )
        short = f"{title_name} short cut uses {lexicon.split()[0]} as the hook image."
        return Script(
            title=title_name,
            hook=hook,
            body=body,
            ending=ending,
            short_cutdown=short,
            claims=list(brief.claims),
            format_name=next_format(previous_format),
            target_seconds=int(topic.get("target_seconds", 480)),
            topic_slug=slug,
            provisional=brief.provisional,
        )
