from modules.risk_analyzer import analyze_risk
def test_password_field_is_only_indicator():
    extracted = {"password_input_count": 1, "external_form_actions": [], "text": "Sign in to your account"}
    result = analyze_risk("https://example.com", "https://example.com", "<form><input type='password'></form>", extracted)
    signals = result["categories"]["Phishing indicators"]
    assert any(s["finding"] == "Password field present" for s in signals)
    assert all(s["status"] == "potential indicator, not confirmation" for s in signals)
def test_no_signals_message_is_qualified():
    extracted = {"password_input_count": 0, "external_form_actions": [], "text": "A normal page"}
    result = analyze_risk("https://example.com", "https://example.com", "<p>A normal page</p>", extracted)
    assert result["assessment"] == "No significant indicators detected by implemented checks"
