import pytest
from modules.url_validator import normalize_url, validate_public_destination, URLValidationError
def test_normalizes_bare_domain():
    assert normalize_url("example.com") == "https://example.com/"
def test_rejects_bad_scheme():
    with pytest.raises(URLValidationError): normalize_url("file:///etc/passwd")
@pytest.mark.parametrize("url", ["http://localhost", "http://127.0.0.1", "http://10.0.0.1", "http://169.254.1.1", "http://192.168.1.10"])
def test_rejects_local_or_private(url):
    with pytest.raises(URLValidationError): normalize_url(url)
def test_rejects_credentials():
    with pytest.raises(URLValidationError): normalize_url("https://user:pass@example.com")
def test_rejects_redirect_to_private_without_dns():
    with pytest.raises(URLValidationError): validate_public_destination("http://127.0.0.1", resolve_dns=False)
