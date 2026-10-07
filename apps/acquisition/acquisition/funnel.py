import random
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from core.errors import MissingCredentials, PolicyDenied
from core.stats import thompson_shares as _thompson_shares
from acquisition.policy import critique

TOUCH_OFFSETS = (0, 3, 7, 13)


def thompson_shares(cells: list[dict], rng: random.Random | None = None) -> list[float]:
    return _thompson_shares(cells, rng)


def verify_email(status: str) -> bool:
    return status == "valid"


def score_lead(fit: float, intent: float, reach: float) -> float:
    return fit * intent * reach


def enters_outreach(score: float, threshold: float = 0.35) -> bool:
    return score >= threshold


def is_duplicate(email: str, known: set[str]) -> bool:
    return email.lower() in {item.lower() for item in known}


class ApolloSource:
    def __init__(self, api_key: str):
        if not api_key:
            raise MissingCredentials("APOLLO_API_KEY")
        self.api_key = api_key

    def search(self, icp: dict) -> list[dict]:
        import httpx

        response = httpx.post(
            "https://api.apollo.io/api/v1/mixed_people/search",
            headers={"x-api-key": self.api_key},
            json={"person_titles": icp.get("roles", []), "q_organization_keyword_tags": [icp.get("industry", "")]},
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("people", [])


GREETINGS = {"hi": "Namaste", "es": "Hola", "de": "Hallo", "fr": "Bonjour", "pt": "Olá", "it": "Ciao"}
SIGN_OFFS = {"de": "Viele Grüße", "fr": "Cordialement", "es": "Saludos", "pt": "Abraços", "it": "Saluti"}


def lead_language(lead: dict, profile: dict) -> str:
    supported = [code.lower() for code in profile.get("languages", ["en"])] or ["en"]
    language = str(lead.get("language", "")).lower()
    return language if language in supported else supported[0]


def first_touch(lead: dict, profile: dict, angle: str = "proof-first", language: str = "en") -> str:
    proof = profile["proof_points"][0].rstrip(".")
    reason = lead["reason"].rstrip(".")
    name = lead["first_name"]
    if language in GREETINGS:
        name = f"{GREETINGS[language]} {name}"
    if angle == "pain-first":
        text = f"{name}, noticed {reason}. {proof}. Worth a short note on fixing that at {lead['company']}?"
    elif angle == "insight-first":
        text = f"{name}, one pattern we keep seeing: {proof}. At {lead['company']}, {reason}. Useful to compare notes?"
    elif angle == "question-first":
        text = f"{name}, is {reason} on your list this quarter at {lead['company']}? {proof}. Happy to share how."
    else:
        text = f"{name}, {reason}. {proof}. Open to a short note on whether this is relevant at {lead['company']}?"
    if language in SIGN_OFFS:
        text = f"{text}\n\n{SIGN_OFFS[language]}"
    if "http://" in text or "https://" in text:
        raise PolicyDenied("copywriter produced a first-touch link")
    return text


def subject_line(lead: dict, profile: dict, variant: str = "question") -> str:
    company = lead.get("company") or "your team"
    service = (profile.get("services") or ["your funnel"])[0]
    if variant == "observation":
        return f"{company}: {lead.get('reason', service)[:48]}"
    if variant == "first-name":
        return f"{lead.get('first_name', 'Quick')}, a thought on {service}"
    if variant == "company-name":
        return f"{company} + {service}"
    return f"Question about {company}'s {service}"


def follow_up(lead: dict, profile: dict, index: int) -> str:
    insight = profile["proof_points"][min(index, len(profile["proof_points"]) - 1)]
    return f"{lead['first_name']}, a separate data point: {insight}. Worth a reply?"


def in_business_hours(now: datetime, tz_name: str = "Asia/Kolkata") -> bool:
    local = now.astimezone(ZoneInfo(tz_name))
    return local.weekday() < 5 and 9 <= local.hour < 18


class Sequence:
    def __init__(self, lead_id: str, started: datetime):
        self.lead_id = lead_id
        self.started = started
        self.touches_sent = 0
        self.replied = False
        self.unsubscribed = False
        self.frozen = False

    def next_touch(self, now: datetime) -> dict | None:
        if self.replied or self.unsubscribed or self.frozen or self.touches_sent >= len(TOUCH_OFFSETS):
            return None
        due = self.started + timedelta(days=TOUCH_OFFSETS[self.touches_sent])
        if now < due:
            return None
        return {"index": self.touches_sent, "due": due.isoformat()}

    def mark_sent(self) -> None:
        self.touches_sent += 1

    def mark_replied(self) -> None:
        self.replied = True


def mailbox_can_send(mailbox: dict, sent_today: int) -> bool:
    if mailbox.get("paused"):
        return False
    return sent_today < mailbox.get("daily_cap", 30)


def observe_mailbox(mailbox: dict, bounce_rate: float, complaint_rate: float, inbox_rate: float) -> str:
    if bounce_rate >= 0.05 or complaint_rate >= 0.001:
        mailbox["paused"] = True
        return "paused"
    if inbox_rate < 0.9:
        return "alert"
    return "ok"


ESCALATE_LABELS = {"legal", "hostile", "press", "custom_request"}
_PHONE = re.compile(r"\+?\d[\d\s\-()]{7,}\d")


def classify_reply(text: str) -> str:
    lowered = text.lower().strip()
    if lowered.rstrip(".!") in {"stop", "unsubscribe", "opt out", "optout"}:
        return "unsubscribe"
    if any(token in lowered for token in ("unsubscribe", "stop emailing", "remove me", "stop messaging", "do not contact")):
        return "unsubscribe"
    if "out of office" in lowered or "automatic reply" in lowered or "auto-reply" in lowered:
        return "out_of_office"
    if any(token in lowered for token in ("lawyer", "legal action", "sue you", "formal complaint")):
        return "legal"
    if any(token in lowered for token in ("harassment", "report you", "this is spam")):
        return "hostile"
    if any(token in lowered for token in ("journalist", "press enquiry", "press inquiry", "partnership", "partner with you")):
        return "press"
    if any(token in lowered for token in ("custom pricing", "custom scope", "special price", "bigger discount")):
        return "custom_request"
    if requested_channel(text):
        return "channel_switch"
    if any(token in lowered for token in ("not now", "next quarter", "circle back", "later this year")):
        return "not_now"
    if lowered.startswith("talk to") or "talk to " in lowered:
        return "referral"
    if "are you an ai" in lowered or "are you a bot" in lowered or "are you human" in lowered or "is this automated" in lowered:
        return "identity"
    if any(token in lowered for token in ("too expensive", "have an agency", "your price", "no budget", "bad timing", "don't trust")):
        return "objection"
    if any(token in lowered for token in ("interested", "book a", "let's talk", "sounds good", "send details")):
        return "interested"
    return "question"


def requested_channel(text: str) -> dict | None:
    """Detect a prospect asking to move channel; this is the consent that unlocks WhatsApp/SMS/voice."""
    lowered = text.lower()
    channel = None
    if "whatsapp" in lowered and any(token in lowered for token in ("whatsapp me", "on whatsapp", "via whatsapp", "message me", "move to whatsapp")):
        channel = "whatsapp"
    elif any(token in lowered for token in ("text me", "sms me", "send me a text")):
        channel = "sms"
    elif any(token in lowered for token in ("call me", "give me a call", "ring me", "phone me")):
        channel = "voice"
    if channel is None:
        return None
    phone = _PHONE.search(text)
    when = None
    match = re.search(r"(today|tomorrow)(?: at (\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?", lowered)
    if match:
        when = {
            "day": match.group(1),
            "hour": int(match.group(2)) if match.group(2) else None,
            "minute": int(match.group(3) or 0),
            "meridiem": match.group(4),
        }
    return {
        "channel": channel,
        "phone": re.sub(r"[\s\-()]", "", phone.group(0)) if phone else None,
        "when": when,
    }


def resolve_call_time(when: dict | None, now: datetime, tz_name: str = "Asia/Kolkata") -> datetime:
    local = now.astimezone(ZoneInfo(tz_name))
    if not when:
        return now + timedelta(hours=1)
    day = local + timedelta(days=1 if when["day"] == "tomorrow" else 0)
    hour = when.get("hour")
    if hour is None:
        return day.replace(hour=11, minute=0, second=0, microsecond=0)
    if when.get("meridiem") == "pm" and hour < 12:
        hour += 12
    elif when.get("meridiem") is None and hour < 8:
        hour += 12
    return day.replace(hour=hour, minute=when.get("minute", 0), second=0, microsecond=0)


def _corpus(profile: dict, brief: str) -> str:
    parts = [
        profile.get("business_name", ""),
        " ".join(profile.get("services", [])),
        " ".join(profile.get("proof_points", [])),
        " ".join(profile.get("faq", [])),
        " ".join(profile.get("objections", {}).values()) if isinstance(profile.get("objections"), dict) else "",
        brief,
    ]
    return " ".join(parts)


def draft_reply(label: str, message: str, profile: dict, brief: str) -> dict:
    corpus = _corpus(profile, brief)
    if label == "identity":
        text = f"Yes. I'm an AI assistant for {profile['business_name']}."
    elif label == "unsubscribe":
        text = "You're unsubscribed and will not be contacted again."
    elif label in ESCALATE_LABELS:
        return {"text": "I'll confirm that and reply shortly.", "escalate": label, "critic": {"passed": True, "reasons": []}}
    elif label == "out_of_office":
        return {"text": "", "escalate": None, "critic": {"passed": True, "reasons": []}}
    elif label == "channel_switch":
        request = requested_channel(message) or {}
        channel = {"whatsapp": "WhatsApp", "sms": "text", "voice": "a call"}.get(request.get("channel"), "that channel")
        if not request.get("phone"):
            text = f"Happy to switch to {channel}. What number should I use?"
        elif request.get("channel") == "voice":
            text = f"Noted. An AI assistant for {profile['business_name']} will call you at the time you mentioned."
        else:
            text = f"Done. I'll continue on {channel}. Reply STOP there at any time to opt out."
    elif label == "objection":
        library = profile.get("objections", {})
        text = objection_answer(message, library)
        if text is None:
            return {"text": "I'll confirm that and reply shortly.", "escalate": "profile_gap", "critic": {"passed": True, "reasons": []}}
    elif label == "not_now":
        text = "Understood. I'll pause outreach and only write again on the date you mentioned."
    elif label == "interested":
        text = f"Glad this is relevant. {profile['faq'][0]}"
    else:
        numbers = re.findall(r"\d+(?:\.\d+)?%?", message)
        if any(number not in corpus for number in numbers):
            return {
                "text": "I'll confirm that and reply shortly.",
                "escalate": "profile_gap",
                "critic": {"passed": True, "reasons": []},
            }
        if not any(token and token in message.lower() for token in profile.get("faq_terms", [])):
            return {
                "text": "I'll confirm that and reply shortly.",
                "escalate": "profile_gap",
                "critic": {"passed": True, "reasons": []},
            }
        text = profile["faq"][0]
    verdict = critique(text, corpus + " " + text, first_touch=False)
    return {"text": text, "escalate": None, "critic": verdict}


OBJECTION_KINDS = (
    ("price", ("expensive", "price", "budget", "cost")),
    ("agency", ("agency", "in-house", "in house")),
    ("timing", ("timing", "busy", "later", "not the right time")),
    ("trust", ("trust", "proof", "references", "case study")),
)


def objection_answer(message: str, library: dict) -> str | None:
    """Pick the approved answer for the objection raised; never invent one."""
    lowered = message.lower()
    for kind, tokens in OBJECTION_KINDS:
        if any(token in lowered for token in tokens) and library.get(kind):
            return library[kind]
    return None


def pre_call_brief(lead: dict, profile: dict, transcript: list[str]) -> dict:
    owner = [
        f"Lead: {lead.get('first_name', '')} at {lead.get('company', '')} ({lead.get('email', '')})",
        f"Need: {lead.get('need', 'unknown')}",
        f"Authority: {lead.get('authority', 'unknown')}",
        f"Budget: {lead.get('budget', 'unknown')}",
        f"Timeline: {lead.get('timeline', 'unknown')}",
        f"Why we reached out: {lead.get('reason', '')}",
    ]
    owner.extend(f"Fact: {fact.get('text', fact) if isinstance(fact, dict) else fact}" for fact in lead.get("brief_facts", [])[:3])
    objections = [line for line in transcript if "objection" in line.lower() or "price" in line.lower()]
    if objections:
        owner.append("Objections raised: " + " | ".join(objections[:2]))
    agenda = (
        f"Agenda for our call: 1) confirm {lead.get('need') or 'your goals'}, "
        f"2) walk through how {profile['business_name']} handles {', '.join(profile.get('services', [])[:2])}, "
        "3) agree next steps."
    )
    return {"owner": "\n".join(owner), "prospect": agenda}


def recontact_on(message: str, now: datetime) -> datetime:
    match = re.search(r"\d{4}-\d{2}-\d{2}", message)
    if match:
        return datetime.fromisoformat(match.group(0)).replace(tzinfo=now.tzinfo)
    if "tomorrow" in message.lower():
        return now + timedelta(days=1)
    return now + timedelta(days=30)


def referral_lead(message: str, referrer_email: str) -> dict | None:
    match = re.search(r"talk to ([A-Z][a-z]+)", message)
    if not match:
        return None
    name = match.group(1)
    return {"first_name": name, "referred_by": referrer_email, "stage": "sourced"}


def qualification_question(lead: dict) -> str | None:
    for field, prompt in (
        ("need", "What problem should this solve first?"),
        ("authority", "Are you the person who can approve this?"),
        ("budget", "What budget band are you working with?"),
        ("timeline", "When do you want this started?"),
    ):
        if not lead.get(field):
            return prompt
    return None


def assess_qualification(lead: dict, price_floor: float) -> str:
    if lead.get("budget_amount") is not None and lead["budget_amount"] < price_floor:
        return "disqualified"
    needed = ("need", "authority", "budget", "timeline")
    if all(lead.get(field) for field in needed):
        return "qualified"
    return "qualifying"


def book_meeting(lead: dict, profile: dict, calendar, slot: str) -> dict:
    if profile["conversion_definition"] != "qualified_meeting":
        raise PolicyDenied("this profile does not convert on a meeting")
    if lead.get("stage") != "qualified":
        raise PolicyDenied("only qualified leads can be booked")
    event = calendar.book(lead["email"], slot)
    lead["stage"] = "converted"
    lead["automation_frozen"] = True
    return event


def complete_handoff(guard, lead: dict, profile: dict, transcript: list[str]) -> dict:
    package = handoff(lead, profile, transcript)
    guard.frozen.add(lead["email"])
    return package


def apply_unsubscribe(guard, lead_id: str, email: str) -> None:
    guard.suppression.add(email, tenant_id=None)
    guard.replied.add(lead_id)


def handoff(lead: dict, profile: dict, transcript: list[str]) -> dict:
    lead["stage"] = "converted"
    lead["automation_frozen"] = True
    human = profile["human_name"]
    return {
        "briefing": {
            "lead": lead["email"],
            "scope": profile["services"],
            "transcript": transcript,
            "price_floor": profile["price_floor"],
        },
        "message": f"{lead['first_name']}, {human} from {profile['business_name']} will take it from here.",
        "notify": profile.get("notify", "email"),
    }


EVAL_CASES = [
    {
        "message": "Yes. I'm an AI assistant for Northwind.",
        "corpus": "Northwind",
        "first_touch": False,
        "expect_pass": True,
    },
    {
        "message": "We grew revenue 80% last quarter for a client.",
        "corpus": "Northwind runs CRO audits.",
        "first_touch": False,
        "expect_pass": False,
    },
    {
        "message": "See https://northwind.example/demo for the full audit.",
        "corpus": "Northwind",
        "first_touch": True,
        "expect_pass": False,
    },
]


REPLY_EVAL_SET: list[tuple[str, str]] = [
    ("Interested — let's talk next week.", "interested"),
    ("Sounds good, send details.", "interested"),
    ("Can we book a call on Thursday?", "interested"),
    ("Yes, I'm interested in the audit.", "interested"),
    ("Please unsubscribe me.", "unsubscribe"),
    ("STOP", "unsubscribe"),
    ("Remove me from your list.", "unsubscribe"),
    ("Stop emailing me.", "unsubscribe"),
    ("Do not contact me again.", "unsubscribe"),
    ("I am out of office until Monday.", "out_of_office"),
    ("Automatic reply: I'm travelling.", "out_of_office"),
    ("Not now, maybe next quarter.", "not_now"),
    ("Circle back on 2027-01-15.", "not_now"),
    ("Talk to Priya, she runs growth.", "referral"),
    ("You should talk to Arjun about this.", "referral"),
    ("My lawyer will be in touch.", "legal"),
    ("We will take legal action if this continues.", "legal"),
    ("I'm filing a formal complaint.", "legal"),
    ("This is harassment.", "hostile"),
    ("I'll report you for this.", "hostile"),
    ("This is spam.", "hostile"),
    ("Are you an AI?", "identity"),
    ("Are you a bot or a person?", "identity"),
    ("Is this automated?", "identity"),
    ("That's too expensive for us.", "objection"),
    ("We already have an agency.", "objection"),
    ("Your price is higher than others.", "objection"),
    ("We don't trust outside vendors.", "objection"),
    ("I'm a journalist writing about checkout tools.", "press"),
    ("Could we discuss a partnership?", "press"),
    ("Can you do custom pricing for 12 stores?", "custom_request"),
    ("We need a custom scope across three brands.", "custom_request"),
    ("WhatsApp me on +91 98765 43210.", "channel_switch"),
    ("Call me tomorrow at 4 on +1 415 555 0100.", "channel_switch"),
    ("Text me instead.", "channel_switch"),
    ("What does the audit include?", "question"),
    ("How long does it take?", "question"),
    ("Which platforms do you support?", "question"),
]

CLASSIFIER_MIN_ACCURACY = 0.95


def evaluate_classifier(classifier=classify_reply, cases: list[tuple[str, str]] | None = None) -> dict:
    cases = cases or REPLY_EVAL_SET
    failures = []
    per_label: dict[str, dict[str, int]] = {}
    for text, expected in cases:
        got = classifier(text)
        bucket = per_label.setdefault(expected, {"total": 0, "correct": 0})
        bucket["total"] += 1
        if got == expected:
            bucket["correct"] += 1
        else:
            failures.append({"text": text, "expected": expected, "got": got})
    accuracy = (len(cases) - len(failures)) / len(cases) if cases else 0.0
    return {"accuracy": round(accuracy, 4), "cases": len(cases), "per_label": per_label, "failures": failures}


def activate_prompt(
    version: dict,
    cases: list[dict] | None = None,
    classifier=classify_reply,
    baseline_accuracy: float | None = None,
) -> dict:
    """A new agent version ships only if it passes the rubric and matches or beats the current accuracy."""
    cases = cases or EVAL_CASES
    for case in cases:
        verdict = critique(case["message"], case["corpus"], first_touch=case["first_touch"])
        if verdict["passed"] != case["expect_pass"]:
            raise PolicyDenied("prompt version failed the offline rubric")
    result = evaluate_classifier(classifier)
    floor = max(CLASSIFIER_MIN_ACCURACY, baseline_accuracy or 0.0)
    if result["accuracy"] < floor:
        raise PolicyDenied(f"classifier accuracy {result['accuracy']:.2f} is below {floor:.2f}")
    version["active"] = True
    version["eval"] = {"accuracy": result["accuracy"], "cases": result["cases"]}
    return version
