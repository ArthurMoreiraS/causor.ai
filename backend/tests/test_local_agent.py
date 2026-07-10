from app.local_agent.browser import profile_dir


def test_profile_path_is_scoped_by_system_court_and_degree(tmp_path):
    first = profile_dir(tmp_path, "PJe", "TJMG", "1")
    second = profile_dir(tmp_path, "PJe", "TJMG", "2")
    assert first != second
    assert first == tmp_path / "pje" / "tjmg" / "1"
    assert ".." not in first.parts
