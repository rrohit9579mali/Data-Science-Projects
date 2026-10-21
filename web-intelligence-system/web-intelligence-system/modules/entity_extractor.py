"""Optional spaCy NER plus transparent technical-keyword fallback."""
TECH_TERMS = ["Python", "Java", "JavaScript", "SQL", "HTML", "CSS", "React", "Node.js",
              "Streamlit", "Scikit-learn", "PyTorch", "TensorFlow", "machine learning",
              "artificial intelligence", "binary search", "linked list", "neural network",
              "BeautifulSoup", "Playwright", "Trafilatura", "GitHub"]
def extract_entities(text: str) -> dict:
    entities, method = [], "keyword fallback"
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
        doc = nlp(text[:100000])
        entities = [{"text": ent.text, "label": ent.label_, "method": "spaCy NER"}
                    for ent in doc.ents[:100]]
        method = "spaCy en_core_web_sm"
    except Exception:
        entities = []
    lower = (text or "").lower()
    tech = [{"text": term, "label": "TECHNICAL_TERM", "method": "case-insensitive phrase match"}
            for term in TECH_TERMS if term.lower() in lower]
    seen = {(e["text"].lower(), e["label"]) for e in entities}
    entities.extend(e for e in tech if (e["text"].lower(), e["label"]) not in seen)
    return {"entities": entities[:150], "method": method + " + technical keyword fallback",
            "note": "Keyword matches are technical terms, not named entities recognized by an NER model."}
