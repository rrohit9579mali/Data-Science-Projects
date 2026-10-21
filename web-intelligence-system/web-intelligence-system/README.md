# Web Intelligence & Risk Analysis System

An interview-friendly Python/Streamlit MVP that fetches a public HTML page, extracts text, classifies page type using transparent phrase rules, detects topics and inferred intent, and reports explainable security indicators.

## What is implemented

- HTTP/HTTPS URL normalization and validation.
- Rejects local hostnames and non-global IPs; checks DNS resolution and validates redirect destinations.
- Manual redirect handling, request timeout, response-size cap, TLS verification, and HTML content-type check.
- BeautifulSoup metadata/HTML inspection and Trafilatura main-text extraction with fallback.
- Heuristic page-type classification, multi-topic phrase matching, inferred audience/intent.
- Explainable URL/form/password/keyword risk heuristics.
- HTML element-count structure summary, optional spaCy NER with technical-keyword fallback.
- JSON report and extracted-text downloads.
- Unit tests using synthetic HTML.

## Important limitations

This is not a production-grade SSRF boundary, malware scanner, phishing detector, or calibrated ML system. DNS is checked before each request, but Python Requests does not pin the connection to the validated IP, so DNS rebinding and lower-level network edge cases are not fully eliminated. Deploy only with outbound network controls if untrusted users can submit URLs. Playwright rendering, a trained classifier, a labeled dataset, calibrated probabilities, and validated spam detection are not implemented. The application does not submit forms or execute page JavaScript. HTTP requests may still retrieve ordinary HTML from public servers.

The phrase-matching topic scores are matched-phrase fractions, not probabilities. The page classifier is rule-based, not trained ML. Structural percentages describe HTML element counts, not screen area. Keyword fallback items are not true NER predictions.

## Windows PowerShell setup

```powershell
cd path\to\web-intelligence-system
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open the local URL Streamlit prints (usually `http://localhost:8501`).

If PowerShell blocks activation, run this for the current terminal only:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

## Run tests

```powershell
python -m pytest -q
```

Tests use synthetic fixtures and do not require visiting a live website. Live network analysis is performed only when you submit a URL in the UI.

## Manual smoke test

1. Launch the app.
2. Submit `https://www.python.org/`.
3. Inspect title, extracted text, topic evidence, risk heuristics, and metadata.
4. Download the JSON report and extracted text.
5. Also test malformed input and `http://127.0.0.1` (the latter must be rejected).

Actual results depend on the live page and network. Do not present an expected page type or risk result as guaranteed.

## Architecture

`app.py` → `url_validator.py` → `webpage_fetcher.py` → `content_extractor.py` → classification/topic/intent/risk/structure/entity modules → `report_generator.py` → Streamlit display/download.

## Libraries

- Requests: bounded HTTP requests and manual redirect handling.
- BeautifulSoup: inspect HTML tags/forms/links and fallback text extraction.
- Trafilatura: main-content extraction that attempts to reduce boilerplate.
- Streamlit: UI and downloadable reports.
- spaCy (optional, not in required dependencies): NER only if `en_core_web_sm` is already installed.
- Pytest: isolated tests.

## Honest interview summary

“I built an MVP that fetches public HTML with URL and redirect checks, extracts meaningful text, and generates an explainable website-intelligence report. Page type, topics, intent, and risk signals use transparent heuristics rather than a trained model. It includes response limits and warnings, but it is not a production-grade SSRF gateway or a definitive phishing detector. A next step would be building a labeled dataset, benchmarking a baseline, and evaluating precision, recall, and false positives.”
