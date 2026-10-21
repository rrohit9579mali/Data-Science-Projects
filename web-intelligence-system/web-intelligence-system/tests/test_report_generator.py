import json
from modules.report_generator import build_report
def test_report_is_json_serializable():
    fetch = {"requested_url":"https://example.com","final_url":"https://example.com","status_code":200,
             "content_type":"text/html","fetch_duration_seconds":0.1,"redirect_count":0}
    extracted = {"title":"Test","meta_description":"","word_count":1,"character_count":4,
                 "extraction_method":"beautifulsoup_fallback","extraction_status":"limited","warnings":[],"text":"Test"}
    page = {"page_type":"Other","evidence_strength":"Weak evidence","method":"keyword rule scoring",
            "evidence":[],"candidates":[],"explanation":"test"}
    report = build_report(fetch, extracted, page, [], {"audiences":[],"intents":[]},
                          {"categories":{},"signal_count":0,"assessment":"none","disclaimer":"test"},
                          {"distribution":[]}, {"entities":[]})
    assert json.loads(json.dumps(report))["page"]["type"] == "Other"
