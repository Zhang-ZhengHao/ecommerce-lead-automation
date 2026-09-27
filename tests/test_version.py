from services.version import normalize_build_sha


def test_normalize_build_sha_keeps_a_short_printable_revision():
    assert normalize_build_sha("abcdef1234567890") == "abcdef123456"


def test_normalize_build_sha_uses_dev_when_launcher_has_no_revision():
    assert normalize_build_sha("") == "dev"
    assert normalize_build_sha(None) == "dev"
