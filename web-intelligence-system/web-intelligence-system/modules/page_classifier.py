"""Transparent keyword-scoring page-type baseline; not a trained ML model."""
import re
RULES = {
    "Coding Problem": ["constraints", "sample input", "sample output", "given an array", "expected output", "test cases", "time complexity"],
    "Tutorial / Documentation": ["documentation", "installation", "getting started", "tutorial", "api reference", "syntax"],
    "Educational Article": ["learn", "lesson", "course", "explained", "what is", "examples"],
    "News Article": ["breaking news", "reported", "journalist", "published", "news"],
    "Blog Post": ["blog", "my experience", "in this post", "subscribe to our newsletter"],
    "E-commerce Product": ["add to cart", "buy now", "price", "shipping", "product details", "in stock"],
    "Login / Authentication Page": ["sign in", "log in", "password", "forgot password", "two-factor authentication"],
    "Forum / Discussion": ["replies", "discussion", "asked", "answers", "community forum"],
    "Corporate / Business Website": ["about us", "our services", "our company", "contact us", "careers"],
    "Landing Page": ["get started", "start free trial", "request a demo", "sign up today"],
}
def classify_page(title: str, description: str, text: str) -> dict:
    combined = f"{title}\n{description}\n{text}".lower()
    if len(combined.strip()) < 35:
        return {"page_type": "Unknown / Insufficient Evidence", "evidence_strength": "Insufficient evidence",
                "method": "keyword rule scoring", "candidates": [], "evidence": [],
                "explanation": "Too little title, metadata, or page text was available."}
    scores, evidence = {}, {}
    for label, phrases in RULES.items():
        hits = [phrase for phrase in phrases if re.search(r"(?<!\\w)" + re.escape(phrase) + r"(?!\\w)", combined)]
        if hits:
            scores[label] = len(hits)
            evidence[label] = hits[:6]
    if not scores:
        return {"page_type": "Other", "evidence_strength": "Weak evidence", "method": "keyword rule scoring",
                "candidates": [], "evidence": [], "explanation": "No specific page-type phrase rules matched."}
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    best_label, best_score = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0
    strength = "Strong evidence" if best_score >= 3 and best_score > runner_up else (
        "Moderate evidence" if best_score >= 2 and best_score > runner_up else "Weak evidence")
    return {"page_type": best_label, "evidence_strength": strength, "method": "keyword rule scoring",
            "candidates": [{"type": label, "matched_phrase_count": score} for label, score in ranked[1:4]],
            "evidence": evidence[best_label],
            "explanation": f"Matched {best_score} configured phrase(s); this is a heuristic, not a trained classifier."}
