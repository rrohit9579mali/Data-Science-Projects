"""HTML element-count distribution; not rendered visual area."""
from bs4 import BeautifulSoup
def analyze_structure(html: str) -> dict:
    soup = BeautifulSoup(html or "", "html.parser")
    all_nodes = soup.find_all(True)
    total = len(all_nodes)
    groups = {
        "navigation/header elements": len(soup.find_all(["nav", "header"])),
        "footer/aside elements": len(soup.find_all(["footer", "aside"])),
        "main/article elements": len(soup.find_all(["main", "article"])),
    }
    classified = min(total, sum(groups.values()))
    groups["other HTML elements"] = max(0, total - classified)
    return {"total_html_elements": total,
            "distribution": [{"group": k, "element_count": v,
                              "percent_of_html_elements": round(100*v/total, 1) if total else 0.0}
                             for k, v in groups.items()],
            "method": "Counts selected HTML tags; remaining tags are 'other'. Denominator is all parsed HTML elements.",
            "warning": "These are approximate HTML element-count percentages, not screen area or importance."}
