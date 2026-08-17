from src.screening import normalize_text, restricted_qualified, whole_token_matches


def test_normalize_text():
    assert normalize_text("Acme Holdings Ltd") == "acme holdings ltd"


def test_whole_token_matching():
    assert whole_token_matches("Global Data Group", ["Global", "AI"]) == ["Global"]


def test_restricted_qualification():
    assert restricted_qualified(True, False)
    assert restricted_qualified(False, True)
    assert not restricted_qualified(False, False)
