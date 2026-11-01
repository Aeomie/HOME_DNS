from pathlib import Path

from dns_filter.policy import (
    append_to_custom_list,
    list_signature,
    load_allowed_lists,
    load_allowed_records,
    load_blocked_lists,
    load_blocklist,
    set_allowed_active,
    set_blocked_active,
)
from dns_filter.server import UDPParser


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_every_txt_file_in_the_folder_is_loaded(tmp_path: Path) -> None:
    write(tmp_path / "one.txt", "ads.example.com\n")
    write(tmp_path / "two.txt", "tracker.example.com\n")
    write(tmp_path / "notes.md", "ignored.example.com\n")

    assert load_blocklist(tmp_path) == {"ads.example.com", "tracker.example.com"}


def test_blocked_lists_accept_common_formats(tmp_path: Path) -> None:
    write(
        tmp_path / "mixed.txt",
        "\ufeffplain.example.com\n"
        "# comment\n"
        "! adblock comment\n"
        "0.0.0.0 hosts.example.com\n"
        "127.0.0.1 localhost\n"
        "||rule.example.com^\n"
        "Upper.Example.com. # note\n"
        "not a domain line\n"
        "# disabled: off.example.com\n",
    )

    lists = load_blocked_lists(tmp_path)

    assert load_blocklist(tmp_path) == {
        "plain.example.com",
        "hosts.example.com",
        "rule.example.com",
        "upper.example.com",
    }
    assert lists.entries["off.example.com"][1] is False
    assert lists.files[0].skipped == 2


def test_missing_folder_is_empty(tmp_path: Path) -> None:
    assert load_blocklist(tmp_path / "missing") == set()


def test_toggle_changes_every_file_listing_the_domain(tmp_path: Path) -> None:
    write(tmp_path / "one.txt", "# keep this header\nads.example.com\nother.example.com\n")
    write(tmp_path / "two.txt", "0.0.0.0 ads.example.com\n")

    set_blocked_active(tmp_path, "ads.example.com", False)

    assert load_blocklist(tmp_path) == {"other.example.com"}
    assert (tmp_path / "one.txt").read_text(encoding="utf-8").startswith(
        "# keep this header\n# disabled: ads.example.com\n"
    )

    set_blocked_active(tmp_path, "ads.example.com", True)

    assert "ads.example.com" in load_blocklist(tmp_path)


def test_domain_stays_blocked_while_any_file_blocks_it(tmp_path: Path) -> None:
    write(tmp_path / "one.txt", "# disabled: ads.example.com\n")
    write(tmp_path / "two.txt", "ads.example.com\n")

    assert load_blocklist(tmp_path) == {"ads.example.com"}


def test_new_entries_go_to_custom_list_only(tmp_path: Path) -> None:
    write(tmp_path / "downloaded.txt", "ads.example.com\n")
    write(tmp_path / "custom.txt", "first.example.com")

    append_to_custom_list(tmp_path, ["second.example.com"])

    assert (tmp_path / "downloaded.txt").read_text() == "ads.example.com\n"
    assert load_blocklist(tmp_path) == {
        "ads.example.com",
        "first.example.com",
        "second.example.com",
    }


def test_allowed_lists_merge_and_skip_bad_lines(tmp_path: Path) -> None:
    write(tmp_path / "home.txt", "192.168.1.2 nas.home\nno-address.home\n")
    write(tmp_path / "work.txt", "10.0.0.2 printer.work\n")

    assert load_allowed_records(tmp_path) == {
        "nas.home": "192.168.1.2",
        "printer.work": "10.0.0.2",
    }
    assert load_allowed_lists(tmp_path).files[0].skipped == 1

    set_allowed_active(tmp_path, "nas.home", False)

    assert load_allowed_records(tmp_path) == {"printer.work": "10.0.0.2"}


def test_server_reloads_when_a_list_file_is_added(tmp_path: Path) -> None:
    blocked = tmp_path / "blocked"
    allowed = tmp_path / "allowed"
    blocked.mkdir()
    allowed.mkdir()
    write(blocked / "one.txt", "ads.example.com\n")
    server = UDPParser(
        blocked_domains=load_blocklist(blocked),
        blocked_lists_dir=blocked,
        allowed_lists_dir=allowed,
    )
    before = list_signature(blocked)

    write(blocked / "two.txt", "tracker.example.com\n")
    write(allowed / "home.txt", "192.168.1.2 nas.home\n")
    server._refresh_policy_files()

    assert list_signature(blocked) != before
    assert server.blocked_domains == {"ads.example.com", "tracker.example.com"}
    assert server.local_records == {"nas.home": "192.168.1.2"}
