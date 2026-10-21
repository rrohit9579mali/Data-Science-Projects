"""Multi-label topic detection using explicit phrase matches."""
import re
TOPICS = {
    "Python": ["python", "pip install", "python programming"],
    "Java": ["java programming", "jvm", "javac"],
    "Algorithms": ["algorithm", "time complexity", "sorting algorithm", "binary search"],
    "Data Structures": ["data structure", "linked list", "stack", "queue", "binary tree", "hash table"],
    "Machine Learning": ["machine learning", "scikit-learn", "classification model", "training data"],
    "Artificial Intelligence": ["artificial intelligence", " ai ", "generative ai", "large language model"],
    "Cybersecurity": ["cybersecurity", "phishing", "malware", "vulnerability", "credential theft"],
    "Finance": ["finance", "investment", "stock market", "financial"],
    "Education": ["education", "student", "course", "lesson", "tutorial"],
    "Programming Practice": ["sample input", "sample output", "test cases", "coding challenge", "leetcode"],
}
def detect_topics(text: str) -> list[dict]:
    haystack = f" {text.lower()} "
    found = []
    for topic, phrases in TOPICS.items():
        hits = [p.strip() for p in phrases if re.search(r"(?<!\\w)" + re.escape(p.strip()) + r"(?!\\w)", haystack)]
        if hits:
            found.append({"topic": topic, "matched_phrases": hits[:6],
                          "relevance_score": round(len(hits) / len(phrases), 2),
                          "score_type": "matched phrase fraction; not a probability"})
    return sorted(found, key=lambda item: (-item["relevance_score"], item["topic"]))
