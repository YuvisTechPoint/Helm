from youtube.modules.gate import jaccard

PALETTE = ("#1b1f3b", "#f0a202", "#f7f4ef")
SIMILARITY_BLOCK = 0.72


def score_title(title: str) -> float:
    length = len(title)
    length_score = 1.0 if 35 <= length <= 70 else 0.4
    psychology = 0.3 if "psychology" in title.lower() or "why" in title.lower() else 0.0
    return length_score + psychology


def build_variants(topic_title: str, competitor_titles: list[str]) -> dict:
    candidates = [
        f"The psychology of {topic_title}",
        f"Why {topic_title} changes how you decide",
        f"What {topic_title} reveals about habits",
    ]
    thumbnails = []
    for index, words in enumerate(
        [
            topic_title.split()[:3],
            ["Why", topic_title.split()[0]],
            ["The", "pattern"],
        ]
    ):
        text = " ".join(words)[:32]
        thumbnails.append({"text": text, "palette": PALETTE, "contrast": "high", "index": index})

    titles = []
    for title in candidates:
        if any(jaccard(title, other) >= SIMILARITY_BLOCK for other in competitor_titles):
            continue
        titles.append({"title": title, "score": score_title(title)})
    safe_thumbs = []
    for thumb in thumbnails:
        if any(jaccard(thumb["text"], other) >= SIMILARITY_BLOCK for other in competitor_titles):
            continue
        safe_thumbs.append(thumb)
    titles.sort(key=lambda item: item["score"], reverse=True)
    if not titles or not safe_thumbs:
        raise ValueError("packaging blocked: variants matched competitor assets")
    return {"titles": titles[:3], "thumbnails": safe_thumbs[:3], "palette": PALETTE}
