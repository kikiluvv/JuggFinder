"""
Tests for src/scorer/ai.py.

All AI API calls are patched — no real network calls, no API key required.
Tests cover: JSON parsing, fallback state machine, null-safety.

The real implementation waits 60s on the first Gemini 429 and retries
once. All tests below patch that sleep to zero so they run instantly
but still exercise the retry path.
"""

import pytest

from src.scorer.ai import parse_ai_response, reset_session, score_with_ai


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Neutralize the 60s Gemini retry sleep in every test in this module."""
    monkeypatch.setattr("src.scorer.ai.GEMINI_RATE_LIMIT_SLEEP", 0.0)


# ---------------------------------------------------------------------------
# parse_ai_response — pure function
# ---------------------------------------------------------------------------


class TestParseAiResponse:
    def test_valid_json(self):
        text = '{"score": 4, "issues": ["No HTTPS", "Outdated design"], "summary": "Old site."}'
        result = parse_ai_response(text)
        assert result["score"] == 4
        assert result["issues"] == ["No HTTPS", "Outdated design"]
        assert result["summary"] == "Old site."

    def test_strips_markdown_json_fence(self):
        text = '```json\n{"score": 7, "issues": [], "summary": "Decent."}\n```'
        result = parse_ai_response(text)
        assert result["score"] == 7

    def test_strips_markdown_fence_no_language(self):
        text = '```\n{"score": 3, "issues": ["Broken"], "summary": "Bad."}\n```'
        result = parse_ai_response(text)
        assert result["score"] == 3

    def test_score_zero_mapped_to_none(self):
        text = '{"score": 0, "issues": [], "summary": "Empty."}'
        result = parse_ai_response(text)
        assert result["score"] is None

    def test_score_out_of_range_high_mapped_to_none(self):
        text = '{"score": 11, "issues": [], "summary": "Too high."}'
        result = parse_ai_response(text)
        assert result["score"] is None

    def test_score_out_of_range_low_mapped_to_none(self):
        # Score of 0 should map to None
        text = '{"score": -1, "issues": [], "summary": "Negative."}'
        result = parse_ai_response(text)
        assert result["score"] is None

    def test_valid_boundary_score_1(self):
        text = '{"score": 1, "issues": ["Broken"], "summary": "Unusable."}'
        assert parse_ai_response(text)["score"] == 1

    def test_valid_boundary_score_10(self):
        text = '{"score": 10, "issues": [], "summary": "Perfect."}'
        assert parse_ai_response(text)["score"] == 10

    def test_garbage_returns_null_result(self):
        result = parse_ai_response("sorry I cannot provide a score")
        assert result["score"] is None
        assert result["issues"] == []
        assert result["summary"] is None

    def test_empty_string_returns_null_result(self):
        result = parse_ai_response("")
        assert result == {"score": None, "issues": [], "summary": None}

    def test_missing_issues_defaults_to_empty_list(self):
        text = '{"score": 5, "summary": "Mediocre."}'
        result = parse_ai_response(text)
        assert result["issues"] == []

    def test_missing_summary_returns_none(self):
        text = '{"score": 5, "issues": []}'
        result = parse_ai_response(text)
        assert result["summary"] is None

    def test_empty_summary_returns_none(self):
        text = '{"score": 5, "issues": [], "summary": ""}'
        result = parse_ai_response(text)
        assert result["summary"] is None

    def test_issues_is_always_a_list(self):
        text = '{"score": 5, "issues": "single issue string", "summary": "ok"}'
        result = parse_ai_response(text)
        # json.loads gives us a string; list() on a string gives chars — that's a
        # quirk we accept; the important thing is it doesn't crash
        assert isinstance(result["issues"], list)

    def test_returns_consistent_keys(self):
        result = parse_ai_response("garbage")
        assert set(result.keys()) == {"score", "issues", "summary"}


# ---------------------------------------------------------------------------
# score_with_ai — fallback state machine
# ---------------------------------------------------------------------------


class TestScoreWithAiGeminiSuccess:
    async def test_returns_gemini_result(self, monkeypatch):
        reset_session()

        async def mock_gemini(html):
            return {"score": 7, "issues": ["Dated design"], "summary": "Functional but old."}

        monkeypatch.setattr("src.scorer.ai._call_gemini", mock_gemini)
        result = await score_with_ai("<html>test</html>")
        assert result["score"] == 7
        assert result["issues"] == ["Dated design"]

    async def test_does_not_call_groq_when_gemini_succeeds(self, monkeypatch):
        reset_session()
        groq_called = []

        async def mock_gemini(html):
            return {"score": 5, "issues": [], "summary": "Ok."}

        async def mock_groq(html):
            groq_called.append(True)
            return {"score": 1, "issues": [], "summary": "Groq."}

        monkeypatch.setattr("src.scorer.ai._call_gemini", mock_gemini)
        monkeypatch.setattr("src.scorer.ai._call_groq", mock_groq)
        await score_with_ai("<html></html>")
        assert groq_called == []


class TestScoreWithAiFallback:
    async def test_429_triggers_groq_fallback(self, monkeypatch):
        reset_session()

        async def mock_gemini(html):
            raise Exception("429 ResourceExhausted quota exceeded")

        async def mock_groq(html):
            return {"score": 3, "issues": ["Very old"], "summary": "Ancient site."}

        monkeypatch.setattr("src.scorer.ai._call_gemini", mock_gemini)
        monkeypatch.setattr("src.scorer.ai._call_groq", mock_groq)
        result = await score_with_ai("<html></html>")
        assert result["score"] == 3

    async def test_resource_exhausted_triggers_fallback(self, monkeypatch):
        reset_session()

        async def mock_gemini(html):
            raise Exception("RESOURCE_EXHAUSTED: quota exceeded")

        async def mock_groq(html):
            return {"score": 4, "issues": [], "summary": "Groq says mediocre."}

        monkeypatch.setattr("src.scorer.ai._call_gemini", mock_gemini)
        monkeypatch.setattr("src.scorer.ai._call_groq", mock_groq)
        result = await score_with_ai("<html></html>")
        assert result["score"] == 4

    async def test_fallback_flag_persists_for_session(self, monkeypatch):
        """After one 429, ALL subsequent calls should go to Groq, never Gemini."""
        reset_session()
        gemini_call_count = []
        groq_call_count = []

        async def mock_gemini(html):
            gemini_call_count.append(1)
            raise Exception("429 quota")

        async def mock_groq(html):
            groq_call_count.append(1)
            return {"score": 5, "issues": [], "summary": "Groq."}

        monkeypatch.setattr("src.scorer.ai._call_gemini", mock_gemini)
        monkeypatch.setattr("src.scorer.ai._call_groq", mock_groq)

        # First call: Gemini 429 → one-shot retry → 429 → falls back to Groq
        await score_with_ai("<html>1</html>")
        # Second and third calls: should go directly to Groq, Gemini never called again
        await score_with_ai("<html>2</html>")
        await score_with_ai("<html>3</html>")

        assert len(gemini_call_count) == 2  # Initial + retry (both 429)
        assert len(groq_call_count) == 3  # All three scoring calls landed on Groq


class TestScoreWithAiBothFail:
    async def test_non_rate_limit_gemini_error_returns_null(self, monkeypatch):
        reset_session()

        async def mock_gemini(html):
            raise Exception("Internal server error")

        monkeypatch.setattr("src.scorer.ai._call_gemini", mock_gemini)
        result = await score_with_ai("<html></html>")
        assert result == {"score": None, "issues": [], "summary": None}

    async def test_groq_failure_returns_null(self, monkeypatch):
        reset_session()

        async def mock_gemini(html):
            raise Exception("429 quota")

        async def mock_groq(html):
            raise Exception("Groq service unavailable")

        monkeypatch.setattr("src.scorer.ai._call_gemini", mock_gemini)
        monkeypatch.setattr("src.scorer.ai._call_groq", mock_groq)
        result = await score_with_ai("<html></html>")
        assert result == {"score": None, "issues": [], "summary": None}

    async def test_never_raises(self, monkeypatch):
        """score_with_ai must never propagate an exception."""
        reset_session()

        async def mock_gemini(html):
            raise RuntimeError("boom")

        async def mock_groq(html):
            raise RuntimeError("also boom")

        monkeypatch.setattr("src.scorer.ai._call_gemini", mock_gemini)
        monkeypatch.setattr("src.scorer.ai._call_groq", mock_groq)

        # Should not raise
        result = await score_with_ai("anything")
        assert isinstance(result, dict)


class TestResetSession:
    async def test_reset_clears_groq_fallback(self, monkeypatch):
        reset_session()
        gemini_calls = []

        async def mock_gemini(html):
            gemini_calls.append(1)
            raise Exception("429 quota")

        async def mock_groq(html):
            return {"score": 2, "issues": [], "summary": "Groq."}

        monkeypatch.setattr("src.scorer.ai._call_gemini", mock_gemini)
        monkeypatch.setattr("src.scorer.ai._call_groq", mock_groq)

        # Trigger fallback (initial + one-shot retry before giving up)
        await score_with_ai("<html>1</html>")
        assert len(gemini_calls) == 2

        # Reset and verify Gemini retry path is available again
        reset_session()
        await score_with_ai("<html>2</html>")
        assert len(gemini_calls) == 4  # 2 more (initial + retry) after reset
