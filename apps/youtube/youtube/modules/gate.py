import re

from youtube.modules.research import ResearchBrief, Script

SAFETY_PATTERNS = [
    "this is financial advice",
    "this is medical advice",
    "stop your medication",
    "guaranteed returns",
    "you should buy",
]


def tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9']+", text.lower()) if len(token) > 2}


def jaccard(left: str, right: str) -> float:
    a, b = tokens(left), tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class QualityGate:
    def __init__(self, similarity_threshold: float = 0.72):
        self.similarity_threshold = similarity_threshold

    def evaluate(
        self,
        script: Script,
        brief: ResearchBrief,
        competitor_titles: list[str],
        past_scripts: list[str],
        previous_format: str | None = None,
    ) -> dict:
        reasons: list[str] = []
        lowered = script.full_text().lower()
        for pattern in SAFETY_PATTERNS:
            if pattern in lowered:
                return {"decision": "reject", "reasons": [f"safety: {pattern}"], "scores": {}}

        for title in competitor_titles:
            if jaccard(script.title, title) >= self.similarity_threshold:
                reasons.append("title too close to a competitor")
        for past in past_scripts:
            if jaccard(script.full_text(), past) >= self.similarity_threshold:
                reasons.append("script too close to one of our previous scripts")

        urls = brief.source_urls()
        if len(brief.sources) < 5:
            reasons.append("fewer than 5 sources")
        for claim in script.claims:
            if claim.source_url not in urls:
                reasons.append(f"claim missing source: {claim.text}")

        hook_words = script.hook.split()
        if not (8 <= len(hook_words) <= 45):
            reasons.append("hook is outside the first-15-seconds length")
        title_words = {word for word in tokens(script.title) if len(word) > 4}
        hook_tokens = tokens(" ".join(hook_words[:40]))
        if title_words and not (title_words & hook_tokens):
            reasons.append("hook does not restate the title promise")
        if len(script.ending.split()) < 20:
            reasons.append("ending does not pay off the title")
        if previous_format and script.format_name == previous_format:
            reasons.append("format repeats the previous video")
        if not script.short_cutdown.strip():
            reasons.append("missing Short cut-down")

        decision = "pass" if not reasons else "rewrite"
        return {
            "decision": decision,
            "reasons": reasons,
            "scores": {"hook_words": len(hook_words), "claims": len(script.claims)},
        }
