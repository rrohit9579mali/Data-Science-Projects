from modules.content_extractor import extract_content
def test_empty_html():
    result = extract_content("")
    assert result["extraction_status"] == "failed"
    assert result["word_count"] == 0
def test_title_and_text():
    html = "<html><head><title>Python Tutorial</title><meta name='description' content='Learn Python'></head><body><main><h1>Python Tutorial</h1><p>" + ("Python programming tutorial and examples. " * 15) + "</p></main></body></html>"
    result = extract_content(html)
    assert result["title"] == "Python Tutorial"
    assert result["word_count"] > 0
def test_missing_title_is_handled():
    result = extract_content("<html><body><p>Just a short page</p></body></html>")
    assert result["title"] == ""
