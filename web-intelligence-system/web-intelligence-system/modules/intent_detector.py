"""Rule-based audience and intent inference with explicit evidence."""
def infer_audience_intent(title: str, description: str, text: str, page_type: str) -> dict:
    content = f"{title} {description} {text}".lower()
    audiences = []
    checks = [
        ("Students", ["student", "learn", "course", "lesson", "assignment"]),
        ("Developers", ["api", "code", "programming", "developer", "documentation"]),
        ("Professionals", ["enterprise", "business", "industry", "professional"]),
        ("Customers", ["product", "pricing", "buy now", "customer"]),
        ("Researchers", ["research", "paper", "study", "dataset"]),
        ("General readers", ["news", "article", "blog", "guide"]),
    ]
    for label, terms in checks:
        hits = [term for term in terms if term in content]
        if hits:
            audiences.append({"audience": label, "evidence": hits[:4], "status": "inferred"})
    intent_map = [
        ("Practice / Learn", ["tutorial", "lesson", "sample input", "coding challenge", "learn"]),
        ("Read / Research", ["article", "research", "published", "study", "documentation"]),
        ("Purchase", ["add to cart", "buy now", "checkout"]),
        ("Login / Authenticate", ["sign in", "log in", "password"]),
        ("Register", ["sign up", "register", "create account"]),
        ("Discuss", ["discussion", "replies", "forum", "comment"]),
        ("Compare products", ["compare", "comparison", "versus", "vs."]),
        ("Contact a business", ["contact us", "request a demo", "our services"]),
    ]
    intents = []
    for label, terms in intent_map:
        hits = [term for term in terms if term in content]
        if hits:
            intents.append({"intent": label, "evidence": hits[:4], "status": "inferred"})
    return {"audiences": audiences[:4], "intents": intents[:4] or [{"intent": "Unknown", "evidence": [], "status": "insufficient evidence"}]}
