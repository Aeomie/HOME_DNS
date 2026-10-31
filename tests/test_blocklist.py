from pathlib import Path

from dns_filter.blocklist import load_blocklist, normalize_domain


def test_normalize_domain() -> None:
    assert normalize_domain("Example.COM.") == "example.com"


def test_load_blocklist_ignores_comments_and_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "blocked.txt"
    path.write_text(
        "# comment\nAds.Example.com.\n\n tracker.example.net # note\n",
        encoding="utf-8",
    )

    assert load_blocklist(path) == {
        "ads.example.com",
        "tracker.example.net",
    }
