import json

from youtube.modules.research import Claim, ResearchBrief, Script, ScriptWriter, next_format  # noqa: F401


class LlmScriptWriter(ScriptWriter):
    def __init__(self, llm=None):
        self.llm = llm

    def write(self, topic: dict, brief: ResearchBrief, previous_format: str | None = None, rewrite_notes: list[str] | None = None) -> Script:
        if self.llm is None:
            return super().write(topic, brief, previous_format, rewrite_notes)
        system = (
            "Write a faceless YouTube script as JSON with keys title, hook, body, ending, short_cutdown. "
            "Hook must restate the title promise in the first 15 seconds. Every claim must cite a source URL from the brief."
        )
        user = json.dumps(
            {
                "topic": topic,
                "sources": brief.sources,
                "claims": [{"text": c.text, "source_url": c.source_url} for c in brief.claims],
                "rewrite_notes": rewrite_notes or [],
            }
        )
        raw = self.llm.complete(system, user)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return super().write(topic, brief, previous_format, rewrite_notes)
        return Script(
            title=data["title"],
            hook=data["hook"],
            body=data["body"],
            ending=data["ending"],
            short_cutdown=data["short_cutdown"],
            claims=[Claim(text=item["text"], source_url=item["source_url"]) for item in data.get("claims", [])] or list(brief.claims),
            format_name=next_format(previous_format),
            target_seconds=int(topic.get("target_seconds", 480)),
            topic_slug=topic["slug"],
            provisional=brief.provisional,
        )
