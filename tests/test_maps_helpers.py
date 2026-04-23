"""
Unit tests for the pure helper functions in src/scraper/maps.py.

These tests have zero I/O — no Playwright, no DB, no network.
They run fast and should always pass regardless of environment.
"""

from src.scraper.maps import (
    build_search_url,
    extract_place_id_from_url,
    is_end_of_results,
    parse_rating,
    parse_review_count,
)

# ---------------------------------------------------------------------------
# build_search_url
# ---------------------------------------------------------------------------


class TestBuildSearchUrl:
    def test_basic_category(self):
        url = build_search_url("restaurants")
        assert "google.com/maps/search/" in url
        assert "restaurants" in url
        assert "Boise" in url

    def test_multi_word_category(self):
        url = build_search_url("auto repair")
        assert "auto+repair" in url or "auto%20repair" in url

    def test_default_location_is_boise(self):
        url = build_search_url("plumbers")
        assert "Boise" in url
        assert "Idaho" in url

    def test_custom_location(self):
        url = build_search_url("dentist", location="Meridian Idaho")
        assert "Meridian" in url
        assert "dentist" in url

    def test_returns_string(self):
        assert isinstance(build_search_url("HVAC"), str)

    def test_all_13_categories_produce_valid_urls(self):
        from src.config.categories import CATEGORIES

        for cat in CATEGORIES:
            url = build_search_url(cat)
            assert url.startswith("https://www.google.com/maps/search/"), cat
            assert "Boise" in url, cat


# ---------------------------------------------------------------------------
# extract_place_id_from_url
# ---------------------------------------------------------------------------


class TestExtractPlaceIdFromUrl:
    # Real-world ChIJ format (newer)
    CHIJ_URL = (
        "https://www.google.com/maps/place/Goldy%27s+Breakfast+Bistro/"
        "@43.6150169,-116.2023,17z/data=!3m1!4b1!4m6!3m5"
        "!1sChIJN1t_tDeuEmsRUsdiaMB4eJM!8m2!3d43.6150169!4d-116.2023"
    )
    # Hex format (legacy)
    HEX_URL = (
        "https://www.google.com/maps/place/Boise+Fry+Company/"
        "@43.618,-116.204,17z/data=!3m1!4b1"
        "!1s0x54aef872b7d10b1f:0x6e7c1a7d2e3f4a5b!8m2!3d43.618!4d-116.204"
    )

    def test_extracts_chij_place_id(self):
        pid = extract_place_id_from_url(self.CHIJ_URL)
        assert pid == "ChIJN1t_tDeuEmsRUsdiaMB4eJM"

    def test_extracts_hex_place_id(self):
        pid = extract_place_id_from_url(self.HEX_URL)
        assert pid is not None
        assert pid.startswith("0x")

    def test_returns_none_for_search_url(self):
        url = "https://www.google.com/maps/search/restaurants+Boise+Idaho"
        assert extract_place_id_from_url(url) is None

    def test_returns_none_for_empty_string(self):
        assert extract_place_id_from_url("") is None

    def test_returns_none_for_unrelated_url(self):
        assert extract_place_id_from_url("https://example.com") is None

    def test_chij_id_not_truncated(self):
        pid = extract_place_id_from_url(self.CHIJ_URL)
        assert len(pid) > 10  # ChIJ IDs are always longer than 10 chars


# ---------------------------------------------------------------------------
# parse_rating
# ---------------------------------------------------------------------------


class TestParseRating:
    def test_plain_decimal(self):
        assert parse_rating("4.5") == 4.5

    def test_integer_string(self):
        assert parse_rating("4") == 4.0

    def test_with_stars_suffix(self):
        assert parse_rating("4.5 stars") == 4.5

    def test_aria_label_format(self):
        assert parse_rating("4.3 stars out of 5") == 4.3

    def test_european_decimal_comma(self):
        assert parse_rating("4,5") == 4.5

    def test_perfect_score(self):
        assert parse_rating("5.0") == 5.0

    def test_minimum_valid(self):
        # 0.1 > 0 and <= 5, so it is a valid rating
        assert parse_rating("0.1") == 0.1

    def test_zero_returns_none(self):
        assert parse_rating("0") is None
        assert parse_rating("0.0") is None

    def test_above_five_returns_none(self):
        assert parse_rating("5.1") is None
        assert parse_rating("10") is None

    def test_empty_string_returns_none(self):
        assert parse_rating("") is None

    def test_no_numbers_returns_none(self):
        assert parse_rating("no rating") is None

    def test_extracts_from_mixed_text(self):
        assert parse_rating("Rated 3.8 by customers") == 3.8


class TestParseRatingEdgeCases:
    def test_minimum_valid_rating(self):
        # 0.1 > 0 and <= 5, so it should be returned
        result = parse_rating("0.1")
        assert result == 0.1

    def test_exactly_five(self):
        assert parse_rating("5") == 5.0

    def test_5_1_is_none(self):
        assert parse_rating("5.1") is None


# ---------------------------------------------------------------------------
# parse_review_count
# ---------------------------------------------------------------------------


class TestParseReviewCount:
    def test_plain_number(self):
        assert parse_review_count("123") == 123

    def test_parenthesized(self):
        assert parse_review_count("(1,234)") == 1234

    def test_with_reviews_suffix(self):
        assert parse_review_count("456 reviews") == 456

    def test_comma_separated_large_number(self):
        assert parse_review_count("1,234 reviews") == 1234

    def test_abbreviated_k(self):
        assert parse_review_count("1.2K reviews") == 1200

    def test_abbreviated_k_uppercase(self):
        assert parse_review_count("2.5K") == 2500

    def test_abbreviated_k_no_decimal(self):
        assert parse_review_count("3K reviews") == 3000

    def test_aria_label_format(self):
        assert parse_review_count("1,234 reviews, 4.5 stars") == 1234

    def test_single_review(self):
        assert parse_review_count("1 review") == 1

    def test_empty_string_returns_none(self):
        assert parse_review_count("") is None

    def test_no_digits_returns_none(self):
        assert parse_review_count("no reviews yet") is None

    def test_zero(self):
        assert parse_review_count("0") == 0


# ---------------------------------------------------------------------------
# is_end_of_results
# ---------------------------------------------------------------------------


class TestIsEndOfResults:
    def test_reached_end(self):
        assert is_end_of_results("You've reached the end of the list") is True

    def test_no_more_results(self):
        assert is_end_of_results("No more results") is True

    def test_case_insensitive(self):
        assert is_end_of_results("NO MORE RESULTS") is True
        assert is_end_of_results("you've reached the end") is True

    def test_normal_text_is_not_end(self):
        assert is_end_of_results("Goldy's Breakfast Bistro") is False
        assert is_end_of_results("Restaurant") is False
        assert is_end_of_results("") is False

    def test_partial_match(self):
        # Must match one of our exact marker strings
        assert is_end_of_results("You've reached the end of the list") is True
        # Text that doesn't contain our markers is not an end signal
        assert is_end_of_results("reached the end of results") is False
