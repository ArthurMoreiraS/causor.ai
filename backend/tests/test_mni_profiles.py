from app.connectors.mni.profiles import resolve_mni_profile


def test_resolve_known_profile_by_tribunal_and_grau():
    profile = resolve_mni_profile("TJMG", "1")
    assert profile is not None
    assert profile.url_endpoint.startswith("https://pje.tjmg.jus.br/")
    assert profile.verificado is False  # so o credenciamento real confere


def test_resolve_is_case_insensitive_and_fails_closed():
    assert resolve_mni_profile("tjmg", "1") is not None
    assert resolve_mni_profile("TJXX", "1") is None
    assert resolve_mni_profile("TJMG", "3") is None


def test_profile_is_immutable():
    profile = resolve_mni_profile("TJMG", "1")
    try:
        profile.url_endpoint = "https://x"  # type: ignore[misc]
        raised = False
    except AttributeError:
        raised = True
    assert raised
