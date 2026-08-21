# Local application imports
from backend.cookie_policy import (
    cookie_domain_for_origin,
    cookie_transport_for_frontend,
    cookies_require_https,
)


def test_loopback_frontend_allows_http_auth_cookies():
    assert not cookies_require_https("http://localhost:3000")
    assert not cookies_require_https("http://127.0.0.1:3000")


def test_non_loopback_frontend_requires_https_auth_cookies():
    assert cookies_require_https("https://example.test")
    assert cookies_require_https("http://example.test")


def test_explicit_cookie_secure_setting_cannot_downgrade_non_loopback():
    assert cookies_require_https("http://localhost:3000", "true")
    assert not cookies_require_https("http://localhost:3000", "false")
    assert cookies_require_https("https://example.test", "false")
    assert cookies_require_https("http://public.example:8000", "false")


def test_loopback_origin_omits_configured_production_cookie_domain():
    assert cookie_domain_for_origin("http://127.0.0.1:8000", ".example.test") is None
    assert (
        cookie_domain_for_origin("https://api.example.test", ".example.test")
        == ".example.test"
    )


def test_cookie_transport_is_derived_from_configured_frontend_only():
    assert cookie_transport_for_frontend("https://example.test", ".example.test") == (
        True,
        ".example.test",
    )
    assert cookie_transport_for_frontend("http://127.0.0.1:3001", ".example.test") == (
        False,
        None,
    )
