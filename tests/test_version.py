from services.version import APP_VERSION, format_release_identity, normalize_build_sha


def test_app_version_matches_the_first_release_tag():
    assert APP_VERSION == "0.1.0"


def test_format_release_identity_combines_version_and_normalized_build():
    assert (
        format_release_identity("abcdef1234567890")
        == "v0.1.0 · build abcdef123456"
    )


def test_normalize_build_sha_keeps_a_short_printable_revision():
    assert normalize_build_sha("abcdef1234567890") == "abcdef123456"


def test_normalize_build_sha_uses_dev_when_launcher_has_no_revision():
    assert normalize_build_sha("") == "dev"
    assert normalize_build_sha(None) == "dev"
