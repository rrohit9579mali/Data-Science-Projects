"""Explainable heuristic checks. Signals are not proof of maliciousness."""
import ipaddress, re
from urllib.parse import urlsplit, urljoin
SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "rb.gy", "ow.ly"}
SUSPICIOUS_TERMS = ["verify your account", "urgent action", "account suspended", "confirm password", "claim your prize"]
def analyze_risk(requested_url: str, final_url: str, html: str, extracted: dict) -> dict:
    p = urlsplit(final_url)
    host = p.hostname or ""
    signals = []
    def add(category, severity, finding, evidence, explanation):
        signals.append({"category": category, "severity": severity, "finding": finding,
                        "evidence": evidence, "method": "transparent heuristic",
                        "explanation": explanation, "status": "potential indicator, not confirmation"})
    try:
        ipaddress.ip_address(host)
        add("Suspicious signals", "moderate", "IP address used as hostname", [host],
            "IP-hosted pages can be legitimate, but this pattern deserves context.")
    except ValueError:
        pass
    if "@" in requested_url:
        add("Phishing indicators", "moderate", "At-sign in submitted URL", ["@"],
            "An at-sign can obscure the apparent destination in some URL formats.")
    if len(host.split(".")) >= 5:
        add("Suspicious signals", "low", "Many hostname labels", [host],
            "A long subdomain chain can be used for deception, but also occurs legitimately.")
    if host in SHORTENERS:
        add("Suspicious signals", "low", "URL shortener hostname", [host],
            "Shorteners hide the destination until resolved.")
    if p.scheme.lower() != "https":
        add("Suspicious signals", "low", "HTTPS not used", [p.scheme],
            "HTTP lacks transport encryption; this alone does not establish maliciousness.")
    requested_host = urlsplit(requested_url if "://" in requested_url else "https://" + requested_url).hostname or ""
    if requested_host.lower() != host.lower():
        add("Suspicious signals", "moderate", "Cross-host redirect", [f"{requested_host} → {host}"],
            "Redirects can be normal; unexpected host changes should be reviewed.")
    if extracted.get("password_input_count", 0):
        add("Phishing indicators", "low", "Password field present",
            [f"{extracted['password_input_count']} password input(s) detected"],
            "Password fields are common on legitimate login pages; inspect destination and context.")
    for action in extracted.get("external_form_actions", []):
        target = urljoin(final_url, action)
        target_host = urlsplit(target).hostname or ""
        if target_host and target_host.lower() != host.lower():
            add("Phishing indicators", "moderate", "Form submits to a different host",
                [action, f"form host: {target_host}; page host: {host}"],
                "Cross-host form submission may be legitimate, but can expose credentials to another domain.")
    body = (extracted.get("text", "") + " " + (html[:100000] if html else "")).lower()
    matched = [term for term in SUSPICIOUS_TERMS if term in body]
    if len(matched) >= 2:
        add("Phishing indicators", "moderate", "Urgency / credential language combination", matched,
            "A combination of urgency and account-verification phrases can occur in phishing lures.")
    spam_terms = [term for term in ["make money fast", "free prize", "buy followers", "guaranteed income"] if term in body]
    if spam_terms:
        add("Spam indicators", "low", "Potential promotional spam language", spam_terms,
            "These phrases are weak signals and require context; no validated spam model is used.")
    categories = {"Phishing indicators": [], "Spam indicators": [], "Suspicious signals": []}
    for signal in signals:
        categories[signal["category"]].append(signal)
    return {"categories": categories, "signal_count": len(signals),
            "assessment": "Review detected indicators" if signals else "No significant indicators detected by implemented checks",
            "disclaimer": "Heuristics can miss attacks and flag legitimate pages. This is not a malware scanner or a guarantee of safety."}
