from collectors.windows import build_query, parse_events_xml


def event_xml(record_id, event_id, data, time="2026-09-29T14:03:11.1234567Z"):
    fields = "".join(f'<Data Name="{k}">{v}</Data>' for k, v in data.items())
    return (
        '<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
        f"<System><EventID>{event_id}</EventID><TimeCreated SystemTime='{time}'/>"
        f"<EventRecordID>{record_id}</EventRecordID></System>"
        f"<EventData>{fields}</EventData></Event>"
    )


def test_failed_logon():
    xml = event_xml(10, 4625, {"TargetUserName": "alice", "LogonType": "3", "IpAddress": "203.0.113.9"})
    events, max_record = parse_events_xml(xml)
    assert max_record == 10
    assert events == [
        {
            "record_id": "10",
            "event_time": "2026-09-29T14:03:11.123456+00:00",
            "event_type": "login_failure",
            "username": "alice",
            "source_ip": "203.0.113.9",
            "logon_type": "3",
            "source_event_id": "4625",
            "message": "Failed logon for alice (type 3)",
        }
    ]


def test_skips_noise_but_still_advances_record_id():
    xml = (
        event_xml(1, 4624, {"TargetUserName": "SYSTEM", "LogonType": "5"})  # service logon
        + event_xml(2, 4624, {"TargetUserName": "PC01$", "LogonType": "3", "IpAddress": "10.0.0.5"})
        + event_xml(3, 4624, {"TargetUserName": "bob", "LogonType": "3", "IpAddress": "::1"})  # local
        + event_xml(4, 4732, {"TargetUserName": "Remote Desktop Users", "MemberName": "bob"})
    )
    events, max_record = parse_events_xml(xml)
    assert events == []
    assert max_record == 4


def test_interactive_logon_and_admin_group_add():
    xml = event_xml(5, 4624, {"TargetUserName": "bob", "LogonType": "10", "IpAddress": "198.51.100.7"}) + event_xml(
        6, 4732, {"TargetUserName": "Administrators", "MemberName": "CN=eve", "SubjectUserName": "admin"}
    )
    events, _ = parse_events_xml(xml)
    assert [e["event_type"] for e in events] == ["login_success", "admin_group_added"]
    assert events[1]["username"] == "CN=eve"
    assert "Administrators" in events[1]["message"]


def test_dash_ip_becomes_none():
    events, _ = parse_events_xml(event_xml(7, 4625, {"TargetUserName": "x", "LogonType": "2", "IpAddress": "-"}))
    assert events[0]["source_ip"] is None


def test_query_uses_checkpoint_or_lookback():
    assert "EventRecordID > 42" in build_query(42, 24)
    assert "timediff(@SystemTime) <= 86400000" in build_query(None, 24)
