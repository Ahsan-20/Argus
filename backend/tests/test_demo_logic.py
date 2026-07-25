"""Pure demo helpers: target detection. No DB, network, or keys."""

from app.demo import DEMO_CALLSIGN, is_demo_target


def test_is_demo_target_matches_path():
    assert is_demo_target("https://argus.koyeb.app/demo/target")
    assert is_demo_target("http://localhost:8000/demo/target/")


def test_is_demo_target_rejects_others():
    assert not is_demo_target("https://example.com")
    assert not is_demo_target("https://argus.koyeb.app/demo/other")
    assert not is_demo_target("")


def test_demo_callsign_constant():
    assert DEMO_CALLSIGN == "PROBE-DEMO"
