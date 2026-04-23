"""
Tests for src/scraper/evaluator.py.

Structure:
  - Pure helper tests (no I/O): is_social_url, has_mobile_viewport,
    extract_copyright_year, build_early_result, build_full_result
  - evaluate_website() integration tests using httpx's MockTransport
    so we never hit the real network.
"""

import httpx
import pytest_asyncio  # noqa: F401 — needed for async fixture discovery

from src.scraper.evaluator import (
    HTML_SNIPPET_MAX,
    build_early_result,
    build_full_result,
    evaluate_website,
    extract_copyright_year,
    has_mobile_viewport,
    is_social_url,
)

# ---------------------------------------------------------------------------
# Helpers: is_social_url
# ---------------------------------------------------------------------------


class TestIsSocialUrl:
    def test_facebook(self):
        assert is_social_url("https://www.facebook.com/mybiz") is True

    def test_facebook_subdomain(self):
        assert is_social_url("https://business.facebook.com/mybiz") is True

    def test_fb_shortlink(self):
        assert is_social_url("https://fb.com/mybiz") is True

    def test_yelp(self):
        assert is_social_url("https://www.yelp.com/biz/abc") is True

    def test_instagram(self):
        assert is_social_url("https://instagram.com/mybiz") is True

    def test_twitter(self):
        assert is_social_url("https://twitter.com/mybiz") is True

    def test_x_com(self):
        assert is_social_url("https://x.com/mybiz") is True

    def test_google_maps(self):
        assert is_social_url("https://google.com/maps/place/foo") is True

    def test_linkedin(self):
        assert is_social_url("https://linkedin.com/company/mybiz") is True

    def test_tripadvisor(self):
        assert is_social_url("https://www.tripadvisor.com/mybiz") is True

    def test_real_website(self):
        assert is_social_url("https://mybizwebsite.com") is False

    def test_real_website_with_www(self):
        assert is_social_url("https://www.plumbingboise.com") is False

    def test_none_returns_false(self):
        assert is_social_url(None) is False  # type: ignore[arg-type]

    def test_empty_string_returns_false(self):
        assert is_social_url("") is False

    def test_partial_domain_not_matched(self):
        # "notfacebook.com" should NOT match "facebook.com"
        assert is_social_url("https://notfacebook.com") is False

    def test_subdomain_of_non_social_not_matched(self):
        assert is_social_url("https://app.mybusiness.com") is False


# ---------------------------------------------------------------------------
# Helpers: has_mobile_viewport
# ---------------------------------------------------------------------------


class TestHasMobileViewport:
    def test_standard_viewport_tag(self):
        html = '<meta name="viewport" content="width=device-width, initial-scale=1">'
        assert has_mobile_viewport(html) is True

    def test_single_quoted_viewport(self):
        html = "<meta name='viewport' content='width=device-width'>"
        assert has_mobile_viewport(html) is True

    def test_viewport_with_extra_attributes(self):
        html = '<meta id="vp" name="viewport" content="width=device-width">'
        assert has_mobile_viewport(html) is True

    def test_case_insensitive(self):
        html = '<META NAME="VIEWPORT" CONTENT="width=device-width">'
        assert has_mobile_viewport(html) is True

    def test_no_viewport_tag(self):
        html = "<html><head><title>Old Site</title></head><body></body></html>"
        assert has_mobile_viewport(html) is False

    def test_empty_html(self):
        assert has_mobile_viewport("") is False

    def test_viewport_in_body_text(self):
        # Mentions viewport but not in a <meta> tag
        html = "<p>Our site supports viewport scaling.</p>"
        assert has_mobile_viewport(html) is False


# ---------------------------------------------------------------------------
# Helpers: extract_copyright_year
# ---------------------------------------------------------------------------


class TestExtractCopyrightYear:
    def test_copyright_symbol_year(self):
        html = "<footer>© 2014 Acme Corp. All rights reserved.</footer>"
        assert extract_copyright_year(html) == 2014

    def test_copyright_word_year(self):
        html = "<footer>Copyright 2018 My Business</footer>"
        assert extract_copyright_year(html) == 2018

    def test_copyright_symbol_no_space(self):
        html = "<footer>©2011 Business Name</footer>"
        assert extract_copyright_year(html) == 2011

    def test_copyright_c_in_parens(self):
        html = "<footer>(c) 2009 Old Company</footer>"
        assert extract_copyright_year(html) == 2009

    def test_year_in_footer_element(self):
        html = (
            "<html><body>"
            "<p>Some content</p>"
            "<footer><p>© 2016 Boise Plumbing</p></footer>"
            "</body></html>"
        )
        assert extract_copyright_year(html) == 2016

    def test_prefers_footer_over_body(self):
        # Body has a newer year, footer has the real copyright
        html = "<html><body><p>Updated 2023</p><footer>© 2010 Old Site Inc.</footer></body></html>"
        assert extract_copyright_year(html) == 2010

    def test_no_copyright_returns_none(self):
        html = "<html><body><p>Hello world</p></body></html>"
        assert extract_copyright_year(html) is None

    def test_empty_html_returns_none(self):
        assert extract_copyright_year("") is None

    def test_year_range_keeps_first(self):
        # "© 2010–2024" — we want the original year (2010)
        html = "<footer>© 2010–2024 Company Inc.</footer>"
        assert extract_copyright_year(html) == 2010

    def test_modern_year_valid(self):
        html = "<footer>© 2023 Fresh Biz</footer>"
        assert extract_copyright_year(html) == 2023


# ---------------------------------------------------------------------------
# Helpers: build_early_result / build_full_result
# ---------------------------------------------------------------------------


class TestBuildEarlyResult:
    def test_shape_with_all_fields(self):
        r = build_early_result(url="https://example.com", early_lead_score=8, status_code=404)
        assert set(r.keys()) == {
            "website_url",
            "website_status_code",
            "has_ssl",
            "has_mobile_viewport",
            "copyright_year",
            "email",
            "tech_stack",
            "html_snippet",
            "skip_ai",
            "early_lead_score",
        }

    def test_skip_ai_is_true(self):
        r = build_early_result(url=None, early_lead_score=10)
        assert r["skip_ai"] is True

    def test_signal_fields_are_none(self):
        r = build_early_result(url="https://fb.com/biz", early_lead_score=9)
        assert r["has_ssl"] is None
        assert r["has_mobile_viewport"] is None
        assert r["copyright_year"] is None
        assert r["html_snippet"] is None

    def test_early_lead_score_stored(self):
        assert build_early_result(None, 10)["early_lead_score"] == 10
        assert build_early_result("https://yelp.com", 9)["early_lead_score"] == 9
        assert build_early_result("https://broken.com", 8, 500)["early_lead_score"] == 8


class TestBuildFullResult:
    GOOD_HTML = (
        "<html><head>"
        '<meta name="viewport" content="width=device-width">'
        "</head><body><footer>© 2021 My Biz</footer></body></html>"
    )

    def test_skip_ai_is_false(self):
        r = build_full_result("https://example.com", 200, self.GOOD_HTML)
        assert r["skip_ai"] is False

    def test_early_lead_score_is_none(self):
        r = build_full_result("https://example.com", 200, self.GOOD_HTML)
        assert r["early_lead_score"] is None

    def test_has_ssl_true_for_https(self):
        r = build_full_result("https://example.com", 200, self.GOOD_HTML)
        assert r["has_ssl"] is True

    def test_has_ssl_false_for_http(self):
        r = build_full_result("http://example.com", 200, self.GOOD_HTML)
        assert r["has_ssl"] is False

    def test_has_mobile_viewport_detected(self):
        r = build_full_result("https://example.com", 200, self.GOOD_HTML)
        assert r["has_mobile_viewport"] is True

    def test_no_mobile_viewport(self):
        html = "<html><head></head><body></body></html>"
        r = build_full_result("https://example.com", 200, html)
        assert r["has_mobile_viewport"] is False

    def test_copyright_year_extracted(self):
        r = build_full_result("https://example.com", 200, self.GOOD_HTML)
        assert r["copyright_year"] == 2021

    def test_html_snippet_truncated(self):
        long_html = "x" * 10_000
        r = build_full_result("https://example.com", 200, long_html)
        assert len(r["html_snippet"]) == HTML_SNIPPET_MAX

    def test_html_snippet_short_not_padded(self):
        short_html = "<html>short</html>"
        r = build_full_result("https://example.com", 200, short_html)
        assert r["html_snippet"] == short_html

    def test_status_code_stored(self):
        r = build_full_result("https://example.com", 200, self.GOOD_HTML)
        assert r["website_status_code"] == 200


# ---------------------------------------------------------------------------
# evaluate_website() — full decision tree with mocked HTTP
# ---------------------------------------------------------------------------


def _mock_transport(status: int, body: str = "", url: str = "https://example.com"):
    """Build an httpx MockTransport that always returns the given status + body."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=status, text=body, request=request)

    return httpx.MockTransport(handler)


class TestEvaluateWebsiteNoUrl:
    async def test_none_returns_score_10(self):
        result = await evaluate_website(None)
        assert result["early_lead_score"] == 10
        assert result["skip_ai"] is True
        assert result["website_url"] is None

    async def test_empty_string_returns_score_10(self):
        result = await evaluate_website("")
        assert result["early_lead_score"] == 10
        assert result["skip_ai"] is True

    async def test_whitespace_only_returns_score_10(self):
        result = await evaluate_website("   ")
        assert result["early_lead_score"] == 10


class TestEvaluateWebsiteSocialUrl:
    async def test_facebook_returns_score_9(self):
        result = await evaluate_website("https://www.facebook.com/mybiz")
        assert result["early_lead_score"] == 9
        assert result["skip_ai"] is True

    async def test_yelp_returns_score_9(self):
        result = await evaluate_website("https://yelp.com/biz/mybiz")
        assert result["early_lead_score"] == 9

    async def test_instagram_returns_score_9(self):
        result = await evaluate_website("https://instagram.com/mybiz")
        assert result["early_lead_score"] == 9

    async def test_google_maps_returns_score_9(self):
        result = await evaluate_website("https://google.com/maps/place/foo")
        assert result["early_lead_score"] == 9

    async def test_social_url_has_null_signals(self):
        result = await evaluate_website("https://facebook.com/biz")
        assert result["has_ssl"] is None
        assert result["has_mobile_viewport"] is None
        assert result["html_snippet"] is None


class TestEvaluateWebsiteHttpError:
    async def test_404_returns_score_8(self, monkeypatch):
        async def mock_fetch(url):
            return httpx.Response(404, text="Not Found")

        monkeypatch.setattr("src.scraper.evaluator._fetch", mock_fetch)
        result = await evaluate_website("https://deadsite.com/")
        assert result["early_lead_score"] == 8
        assert result["website_status_code"] == 404
        assert result["skip_ai"] is True

    async def test_500_returns_score_8(self, monkeypatch):
        async def mock_fetch(url):
            return httpx.Response(500, text="Server Error")

        monkeypatch.setattr("src.scraper.evaluator._fetch", mock_fetch)
        result = await evaluate_website("https://brokensrv.com/")
        assert result["early_lead_score"] == 8
        assert result["website_status_code"] == 500

    async def test_timeout_returns_score_8(self, monkeypatch):
        async def mock_fetch(url):
            raise httpx.TimeoutException("timeout", request=None)

        monkeypatch.setattr("src.scraper.evaluator._fetch", mock_fetch)
        result = await evaluate_website("https://slow.com/")
        assert result["early_lead_score"] == 8
        assert result["skip_ai"] is True

    async def test_connect_error_returns_score_8(self, monkeypatch):
        async def mock_fetch(url):
            raise httpx.ConnectError("refused")

        monkeypatch.setattr("src.scraper.evaluator._fetch", mock_fetch)
        result = await evaluate_website("https://unreachable.com/")
        assert result["early_lead_score"] == 8


class TestEvaluateWebsiteRealSite:
    GOOD_HTML = (
        "<html><head>"
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "</head><body>"
        "<p>Welcome to our plumbing business!</p>"
        "<footer>© 2014 Boise Plumbing Co. All rights reserved.</footer>"
        "</body></html>"
    )
    OLD_HTML = (
        "<html><head></head><body>"
        "<p>Welcome</p>"
        "<footer>Copyright 2008 Old Biz</footer>"
        "</body></html>"
    )

    async def test_good_site_skip_ai_false(self, monkeypatch):
        async def mock_fetch(url):
            return httpx.Response(200, text=self.GOOD_HTML, request=httpx.Request("GET", url))

        monkeypatch.setattr("src.scraper.evaluator._fetch", mock_fetch)
        result = await evaluate_website("https://boiseplumbing.com")
        assert result["skip_ai"] is False
        assert result["early_lead_score"] is None

    async def test_https_detected(self, monkeypatch):
        async def mock_fetch(url):
            return httpx.Response(200, text=self.GOOD_HTML, request=httpx.Request("GET", url))

        monkeypatch.setattr("src.scraper.evaluator._fetch", mock_fetch)
        result = await evaluate_website("https://boiseplumbing.com")
        assert result["has_ssl"] is True

    async def test_no_https_detected(self, monkeypatch):
        async def mock_fetch(url):
            # Simulate redirect: final URL stays http
            req = httpx.Request("GET", "http://oldsite.com")
            return httpx.Response(200, text=self.OLD_HTML, request=req)

        monkeypatch.setattr("src.scraper.evaluator._fetch", mock_fetch)
        result = await evaluate_website("http://oldsite.com")
        assert result["has_ssl"] is False

    async def test_mobile_viewport_detected(self, monkeypatch):
        async def mock_fetch(url):
            return httpx.Response(200, text=self.GOOD_HTML, request=httpx.Request("GET", url))

        monkeypatch.setattr("src.scraper.evaluator._fetch", mock_fetch)
        result = await evaluate_website("https://boiseplumbing.com")
        assert result["has_mobile_viewport"] is True

    async def test_no_mobile_viewport(self, monkeypatch):
        async def mock_fetch(url):
            return httpx.Response(200, text=self.OLD_HTML, request=httpx.Request("GET", url))

        monkeypatch.setattr("src.scraper.evaluator._fetch", mock_fetch)
        result = await evaluate_website("https://oldsite.com")
        assert result["has_mobile_viewport"] is False

    async def test_copyright_year_extracted(self, monkeypatch):
        async def mock_fetch(url):
            return httpx.Response(200, text=self.GOOD_HTML, request=httpx.Request("GET", url))

        monkeypatch.setattr("src.scraper.evaluator._fetch", mock_fetch)
        result = await evaluate_website("https://boiseplumbing.com")
        assert result["copyright_year"] == 2014

    async def test_old_site_copyright_year(self, monkeypatch):
        async def mock_fetch(url):
            return httpx.Response(200, text=self.OLD_HTML, request=httpx.Request("GET", url))

        monkeypatch.setattr("src.scraper.evaluator._fetch", mock_fetch)
        result = await evaluate_website("https://oldsite.com")
        assert result["copyright_year"] == 2008

    async def test_html_snippet_included(self, monkeypatch):
        async def mock_fetch(url):
            return httpx.Response(200, text=self.GOOD_HTML, request=httpx.Request("GET", url))

        monkeypatch.setattr("src.scraper.evaluator._fetch", mock_fetch)
        result = await evaluate_website("https://boiseplumbing.com")
        assert result["html_snippet"] is not None
        assert len(result["html_snippet"]) <= HTML_SNIPPET_MAX

    async def test_url_without_scheme_gets_https(self, monkeypatch):
        """URLs without a scheme should have https:// prepended."""
        received_url: list[str] = []

        async def mock_fetch(url):
            received_url.append(url)
            return httpx.Response(200, text=self.GOOD_HTML, request=httpx.Request("GET", url))

        monkeypatch.setattr("src.scraper.evaluator._fetch", mock_fetch)
        await evaluate_website("mybusiness.com")
        assert received_url[0].startswith("https://")

    async def test_result_always_has_all_keys(self, monkeypatch):
        """Every code path must return a dict with the exact same key set."""
        expected_keys = {
            "website_url",
            "website_status_code",
            "has_ssl",
            "has_mobile_viewport",
            "copyright_year",
            "email",
            "tech_stack",
            "html_snippet",
            "skip_ai",
            "early_lead_score",
        }

        async def mock_fetch(url):
            return httpx.Response(200, text="<html></html>", request=httpx.Request("GET", url))

        monkeypatch.setattr("src.scraper.evaluator._fetch", mock_fetch)

        cases = [
            None,
            "",
            "https://facebook.com/biz",
            "https://example.com",
        ]
        for case in cases:
            result = await evaluate_website(case)
            assert set(result.keys()) == expected_keys, f"Missing keys for input: {case!r}"
