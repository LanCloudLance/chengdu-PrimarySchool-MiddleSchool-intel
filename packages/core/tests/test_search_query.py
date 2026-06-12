from chengdu_edu_core.search_query import _search_patterns


def test_search_patterns_normalize_city_prefix():
    patterns = _search_patterns("成都市棕北小学")
    assert "成都市棕北小学" in patterns
    assert "棕北小学" in patterns


def test_search_patterns_short_name_token():
    patterns = _search_patterns("棕北")
    assert "棕北" in patterns
