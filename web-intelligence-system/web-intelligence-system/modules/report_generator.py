"""Serializable JSON report assembly."""
from datetime import datetime, timezone
def build_report(fetch: dict, extracted: dict, page: dict, topics: list, intent: dict,
                 risk: dict, structure: dict, entities: dict) -> dict:
    return {
        "report_title": "WEBSITE INTELLIGENCE",
        "page": {"type": page["page_type"], "evidence_strength": page["evidence_strength"],
                 "classification_method": page["method"], "classification_evidence": page["evidence"],
                 "alternative_candidates": page["candidates"], "explanation": page["explanation"]},
        "content": {"title": extracted["title"], "description": extracted["meta_description"],
                    "topics": topics, "audience": intent["audiences"], "intents": intent["intents"],
                    "word_count": extracted["word_count"], "character_count": extracted["character_count"],
                    "extraction_method": extracted["extraction_method"],
                    "extraction_status": extracted["extraction_status"]},
        "risk": risk,
        "structure": structure,
        "entities": entities,
        "clean_content": extracted["text"],
        "metadata": {"requested_url": fetch["requested_url"], "final_url": fetch["final_url"],
                     "http_status": fetch["status_code"], "content_type": fetch["content_type"],
                     "fetch_duration_seconds": fetch["fetch_duration_seconds"],
                     "redirect_count": fetch["redirect_count"],
                     "analysis_timestamp_utc": datetime.now(timezone.utc).isoformat(),
                     "warnings": extracted["warnings"]},
    }
