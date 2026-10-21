"""Extract metadata and main text from HTML."""
from bs4 import BeautifulSoup
import trafilatura
from config import MIN_TEXT_CHARS

def extract_content(html: str) -> dict:
    if not isinstance(html, str) or not html.strip():
        return {
            "title": "", "meta_description": "", "canonical_url": None, "text": "",
            "word_count": 0, "character_count": 0, "extraction_method": "none",
            "extraction_status": "failed", "html_element_count": 0,
            "navigation_element_count": 0, "boilerplate_element_count": 0,
            "form_count": 0, "password_input_count": 0, "external_form_actions": [],
            "links": [], "warnings": ["Empty HTML received."],
        }
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    meta = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "description"})
    description = meta.get("content", "").strip() if meta else ""
    canonical = soup.find("link", rel=lambda x: x and "canonical" in ([v.lower() for v in x] if isinstance(x, list) else str(x).lower()))
    canonical_url = canonical.get("href") if canonical else None

    html_count = len(soup.find_all(True))
    nav_count = len(soup.find_all(["nav", "header"]))
    boilerplate_count = len(soup.find_all(["footer", "aside"]))
    form_count = len(soup.find_all("form"))
    password_count = len(soup.select('input[type="password"]'))
    form_actions = [f.get("action", "") for f in soup.find_all("form") if f.get("action")]
    links = [a.get("href", "") for a in soup.find_all("a", href=True)][:500]

    for node in soup(["script", "style", "noscript", "svg", "template"]):
        node.decompose()
    for node in soup.find_all(["nav", "footer", "aside"]):
        node.decompose()
    cleaned_soup_text = soup.get_text(" ", strip=True)

    extracted = None
    try:
        extracted = trafilatura.extract(html, include_comments=False, include_tables=True,
                                        favor_precision=True)
    except Exception:
        extracted = None
    if extracted and len(extracted.strip()) >= MIN_TEXT_CHARS:
        text, method = extracted.strip(), "trafilatura"
    elif cleaned_soup_text:
        text, method = cleaned_soup_text, "beautifulsoup_fallback"
    else:
        text, method = "", "none"
    warnings = []
    status = "success" if len(text) >= MIN_TEXT_CHARS else "limited"
    if status != "success":
        warnings.append("Little meaningful text was extracted; classification may be unreliable.")
    return {
        "title": title, "meta_description": description, "canonical_url": canonical_url,
        "text": text, "word_count": len(text.split()), "character_count": len(text),
        "extraction_method": method, "extraction_status": status,
        "html_element_count": html_count, "navigation_element_count": nav_count,
        "boilerplate_element_count": boilerplate_count, "form_count": form_count,
        "password_input_count": password_count, "external_form_actions": form_actions,
        "links": links, "warnings": warnings,
    }
