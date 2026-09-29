from datetime import datetime, timezone

from collectors.linux import LinuxCollector, parse_line

NOW = datetime(2026, 9, 29, 15, 0, tzinfo=timezone.utc)


def test_failed_password_iso_timestamp():
    line = "2026-09-29T14:03:11.500000+00:00 web01 sshd[812]: Failed password for invalid user admin from 203.0.113.9 port 50122 ssh2"
    event = parse_line(line, "1:0", NOW)
    assert event["event_type"] == "login_failure"
    assert event["username"] == "admin"
    assert event["source_ip"] == "203.0.113.9"
    assert event["event_time"] == "2026-09-29T14:03:11.500000+00:00"
    assert event["logon_type"] == "ssh"


def test_accepted_publickey_classic_timestamp():
    line = "Sep 29 14:05:00 web01 sshd[900]: Accepted publickey for deploy from 198.51.100.4 port 4000 ssh2"
    event = parse_line(line, "1:100", NOW)
    assert event["event_type"] == "login_success"
    assert event["username"] == "deploy"
    assert event["event_time"].startswith("2026-09-")


def test_user_created_and_sudo_group():
    created = parse_line("Sep 29 14:06:00 web01 useradd[1]: new user: name=eve, UID=1002, GID=1002", "1:1", NOW)
    sudo = parse_line("Sep 29 14:06:05 web01 usermod[2]: add 'eve' to group 'sudo'", "1:2", NOW)
    assert (created["event_type"], created["username"]) == ("account_created", "eve")
    assert (sudo["event_type"], sudo["username"]) == ("admin_group_added", "eve")


def test_ignores_unrelated_lines():
    assert parse_line("Sep 29 14:07:00 web01 CRON[5]: pam_unix(cron:session): session opened", "1:3", NOW) is None
    assert parse_line("garbage", "1:4", NOW) is None


def test_collector_reads_only_new_complete_lines(tmp_path):
    log = tmp_path / "auth.log"
    state = tmp_path / "state.json"
    log.write_text(
        "Sep 29 14:00:00 h sshd[1]: Failed password for root from 203.0.113.1 port 1 ssh2\n"
        "Sep 29 14:00:01 h sshd[1]: Failed password for root from 203.0.113.1 port 2 ssh2\n"
        "Sep 29 14:00:02 h sshd[1]: Failed password for ro",  # still being written
        encoding="utf-8",
    )
    collector = LinuxCollector({"linux_log_path": str(log), "state_file": str(state)})
    assert len(collector.collect()) == 2
    collector.commit()

    with open(log, "a", encoding="utf-8") as f:
        f.write("ot from 203.0.113.1 port 3 ssh2\n")
    collector = LinuxCollector({"linux_log_path": str(log), "state_file": str(state)})
    new = collector.collect()
    assert len(new) == 1 and new[0]["username"] == "root"


def test_uncommitted_events_are_collected_again(tmp_path):
    log = tmp_path / "auth.log"
    log.write_text("Sep 29 14:00:00 h sshd[1]: Failed password for root from 203.0.113.1 port 1 ssh2\n")
    config = {"linux_log_path": str(log), "state_file": str(tmp_path / "state.json")}
    first = LinuxCollector(config).collect()  # simulate: server unreachable, no commit
    again = LinuxCollector(config).collect()
    assert first == again
