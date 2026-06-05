from chengdu_edu_core.hashing import content_hash


def test_content_hash_is_64_char_hex():
    result = content_hash("hello")
    assert len(result) == 64
    assert all(c in "0123456789abcdef" for c in result)


def test_content_hash_is_deterministic():
    text = "成都市锦江区招生政策"
    assert content_hash(text) == content_hash(text)
