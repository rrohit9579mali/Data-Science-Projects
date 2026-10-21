from modules.page_classifier import classify_page
from modules.topic_detector import detect_topics
from modules.intent_detector import infer_audience_intent
def test_coding_problem_detection():
    result = classify_page("Array Problem", "", "Given an array, return expected output. Constraints and sample input sample output test cases.")
    assert result["page_type"] == "Coding Problem"
    assert result["evidence"]
def test_insufficient_evidence():
    assert classify_page("", "", "")["page_type"] == "Unknown / Insufficient Evidence"
def test_topics_are_evidence_based():
    topics = detect_topics("Python programming and machine learning with scikit-learn")
    labels = {t["topic"] for t in topics}
    assert "Python" in labels and "Machine Learning" in labels
def test_intent_is_inferred():
    result = infer_audience_intent("Python tutorial", "", "Learn programming with examples", "Tutorial / Documentation")
    assert result["intents"][0]["status"] == "inferred"
