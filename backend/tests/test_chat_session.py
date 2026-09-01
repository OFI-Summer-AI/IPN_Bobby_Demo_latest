from api.commands.ticket_commands import (
    _SESSION_TTL_SECONDS,
    _action_key,
    _fill_step,
    _get_sess,
    _sessions,
)


def setup_function():
    _sessions.clear()


def test_contact_validation_does_not_advance_on_invalid_input():
    session = _get_sess("contact-test")
    session["current_step"] = 1
    valid, error = _fill_step(session, "not-an-email")
    assert valid is False
    assert error
    assert session["current_step"] == 1

    valid, error = _fill_step(session, "Actually, my email is USER@EXAMPLE.COM")
    assert valid is True
    assert error is None
    assert session["contact_email"] == "user@example.com"
    assert session["current_step"] == 2


def test_expired_sessions_are_removed():
    expired = _get_sess("expired")
    expired["last_activity"] -= _SESSION_TTL_SECONDS + 1
    _get_sess("current")
    assert "expired" not in _sessions
    assert "current" in _sessions


def test_action_keys_are_stable_and_distinguish_different_actions():
    pending = {"data": {"subject": "VPN", "priority": "high"}}
    assert _action_key("create_ticket", pending) == _action_key(
        "create_ticket", {"data": {"priority": "high", "subject": "VPN"}}
    )
    assert _action_key("create_ticket", pending) != _action_key("password_reset", pending)
