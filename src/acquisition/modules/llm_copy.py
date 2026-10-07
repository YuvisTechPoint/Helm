import json

from acquisition.funnel import first_touch, lead_language


class LlmCopywriter:
    def __init__(self, llm=None):
        self.llm = llm

    def first_touch(self, lead: dict, profile: dict, angle: str = "proof-first") -> str:
        language = lead_language(lead, profile)
        if self.llm is None:
            return first_touch(lead, profile, angle=angle, language=language)
        system = (
            "Write a cold email first touch under 120 words, no links, no invented numbers, "
            "one proof point from the profile, and a single question close. "
            f"Use the '{angle}' angle. Write in language code '{language}' with culturally appropriate tone "
            "for the prospect's region; keep the facts identical to the profile."
        )
        user = json.dumps({"lead": lead, "profile": profile})
        return self.llm.complete(system, user).strip()


class LlmCritic:
    def __init__(self, llm=None):
        self.llm = llm

    def critique(self, message: str, corpus: str, *, first_touch: bool) -> dict:
        from acquisition.policy import critique

        rule = critique(message, corpus, first_touch=first_touch)
        if not self.llm or rule["passed"]:
            return rule
        system = "Return JSON {passed: bool, reasons: string[]}. Reject spam, links on first touch, invented numbers."
        user = json.dumps({"message": message, "corpus": corpus, "first_touch": first_touch, "rule_reasons": rule["reasons"]})
        try:
            data = json.loads(self.llm.complete(system, user))
            return {"passed": bool(data.get("passed")), "reasons": data.get("reasons", rule["reasons"])}
        except Exception:
            return rule
