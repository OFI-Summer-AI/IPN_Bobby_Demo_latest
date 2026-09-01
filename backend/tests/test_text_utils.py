from text_utils import (
    extract_email,
    extract_message_text,
    extract_phone,
    is_valid_contact_name,
    normalize_query,
)


def test_extract_message_text():
    assert extract_message_text("hello world") == "hello world"
    assert extract_message_text(["hello", "world"]) == "hello world"
    assert extract_message_text([{"type": "text", "text": "hello"}, {"type": "text", "text": "world"}]) == "hello world"
    assert extract_message_text(None) == ""
    assert extract_message_text(123) == "123"


def test_normalize_query_repairs_common_it_typos():
    assert normalize_query("  My WFI is not CONECTED  ") == "my wifi is not connected"
    assert normalize_query("Lapotp pasword issue") == "laptop password issue"


def test_normalize_query_standardizes_apostrophes_and_spacing():
    assert normalize_query("I  can’t   login") == "i can't login"


def test_contact_helpers_extract_normalized_values():
    assert extract_email("Actually, use USER.Name@example.com please") == "user.name@example.com"
    assert extract_phone("Call me on +91 (98765) 43210") == "+91 (98765) 43210"


def test_contact_name_validation_rejects_workflow_commands():
    assert is_valid_contact_name("John Michael Smith")
    assert not is_valid_contact_name("Please create a ticket")
