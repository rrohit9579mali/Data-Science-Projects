import json
import streamlit as st
from config import APP_TITLE
from modules.url_validator import URLValidationError, validate_public_destination
from modules.webpage_fetcher import fetch_webpage, FetchError
from modules.content_extractor import extract_content
from modules.page_classifier import classify_page
from modules.topic_detector import detect_topics
from modules.intent_detector import infer_audience_intent
from modules.risk_analyzer import analyze_risk
from modules.structure_analyzer import analyze_structure
from modules.entity_extractor import extract_entities
from modules.report_generator import build_report

st.set_page_config(page_title=APP_TITLE, page_icon="🔎", layout="wide")
st.title("🔎 Website Intelligence & Risk Analysis")
st.caption("Analyze webpage content, understand its purpose, and inspect potential security signals.")
st.warning("Educational MVP: automated checks can miss malicious pages or flag legitimate ones. No result guarantees that a website is safe. Do not enter credentials based on this report.")

with st.form("analysis_form"):
    submitted_url = st.text_input("Public webpage URL", placeholder="https://example.com")
    submitted = st.form_submit_button("Analyze Website", type="primary")

if submitted:
    try:
        normalized = validate_public_destination(submitted_url)
        with st.spinner("Fetching and analyzing the webpage…"):
            fetch = fetch_webpage(normalized)
            extracted = extract_content(fetch["html"])
            page = classify_page(extracted["title"], extracted["meta_description"], extracted["text"])
            topics = detect_topics(extracted["text"])
            intent = infer_audience_intent(extracted["title"], extracted["meta_description"], extracted["text"], page["page_type"])
            risk = analyze_risk(fetch["requested_url"], fetch["final_url"], fetch["html"], extracted)
            structure = analyze_structure(fetch["html"])
            entities = extract_entities(extracted["text"])
            report = build_report(fetch, extracted, page, topics, intent, risk, structure, entities)
        st.session_state["latest_report"] = report
        st.session_state["latest_text"] = extracted["text"]
    except URLValidationError as exc:
        st.error(f"URL validation failed: {exc}")
    except FetchError as exc:
        st.error(f"Fetch failed ({exc.category}): {exc}")
    except Exception as exc:
        st.error(f"Analysis failed ({type(exc).__name__}): {exc}")

report = st.session_state.get("latest_report")
if report:
    meta, content, page, risk = report["metadata"], report["content"], report["page"], report["risk"]
    st.divider()
    st.subheader("Analysis Summary")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("HTTP status", meta["http_status"])
    c2.metric("Extracted words", content["word_count"])
    c3.metric("Risk signals", risk["signal_count"])
    c4.metric("Extraction", content["extraction_status"].title())
    st.markdown("### Page classification")
    st.write(f"**Type:** {page['type']}  ·  **Evidence strength:** {page['evidence_strength']}")
    st.write(page["explanation"])
    if page["classification_evidence"]:
        st.write("**Matched evidence:** " + ", ".join(page["classification_evidence"]))
    if page["alternative_candidates"]:
        st.write("**Alternative candidates:** " + ", ".join(x["type"] for x in page["alternative_candidates"]))
    st.markdown("### Content intelligence")
    st.write(f"**Title:** {content['title'] or 'Not found'}")
    st.write(f"**Description:** {content['description'] or 'Not found'}")
    st.write(f"**Topics:** {', '.join(t['topic'] for t in content['topics']) or 'No configured topic phrases matched'}")
    st.write("**Possible audiences:** " + ", ".join(a["audience"] for a in content["audience"]) if content["audience"] else "**Possible audiences:** Insufficient evidence")
    st.write("**Possible intents:** " + ", ".join(i["intent"] for i in content["intents"]))
    with st.expander("Topic evidence"):
        st.json(content["topics"])
    with st.expander("Audience and intent evidence"):
        st.json({"audience": content["audience"], "intents": content["intents"]})
    st.markdown("### Security indicators")
    st.write(f"**Assessment:** {risk['assessment']}")
    for category, items in risk["categories"].items():
        with st.expander(f"{category} ({len(items)})", expanded=bool(items)):
            if not items:
                st.write("No indicators detected by the implemented checks.")
            for item in items:
                st.markdown(f"**{item['severity'].title()} — {item['finding']}**")
                st.write(item["explanation"])
                st.caption("Evidence: " + "; ".join(item["evidence"]))
    st.caption(risk["disclaimer"])
    st.markdown("### HTML structure")
    st.write(report["structure"]["method"])
    st.dataframe(report["structure"]["distribution"], use_container_width=True, hide_index=True)
    st.caption(report["structure"]["warning"])
    st.markdown("### Extracted entities and technical terms")
    st.write(report["entities"]["note"])
    st.dataframe(report["entities"]["entities"], use_container_width=True, hide_index=True)
    with st.expander("Metadata and warnings"):
        st.json(meta)
    with st.expander("Extracted clean content"):
        st.text(report["clean_content"] or "No content extracted.")
    st.download_button("Download JSON report", json.dumps(report, ensure_ascii=False, indent=2),
                       file_name="website_intelligence_report.json", mime="application/json")
    st.download_button("Download extracted text", report["clean_content"],
                       file_name="extracted_webpage.txt", mime="text/plain")
