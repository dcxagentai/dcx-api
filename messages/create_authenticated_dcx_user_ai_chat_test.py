from messages import create_authenticated_dcx_user_ai_chat as ai_chat_module
from messages.create_authenticated_dcx_user_ai_chat import create_authenticated_dcx_user_ai_chat


class _FakeCursor:
    def __init__(self, fetchone_values):
        self.fetchone_values = list(fetchone_values)
        self.executed_sql = []

    def execute(self, sql, params=None):
        self.executed_sql.append((" ".join(sql.split()), params))

    def fetchone(self):
        if not self.fetchone_values:
            return None
        return self.fetchone_values.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConnection:
    def __init__(self, cursor):
        self.cursor_instance = cursor

    def cursor(self):
        return self.cursor_instance

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _ConnectFactory:
    def __init__(self, connections):
        self._connections = list(connections)

    def __call__(self, **_kwargs):
        return self._connections.pop(0)


def test_creates_direct_ai_chat_with_hidden_ready_source_message(monkeypatch) -> None:
    monkeypatch.setattr(ai_chat_module, "record_dcx_user_llm_usage_event", lambda **_kwargs: None)
    monkeypatch.setattr(ai_chat_module, "record_dcx_user_activity_event", lambda **_kwargs: None)

    connection = _FakeConnection(
        _FakeCursor(
            [
                (77,),
                (7001,),
                (8001,),
                (9001,),
            ]
        )
    )

    result = create_authenticated_dcx_user_ai_chat(
        authenticated_user_id=77,
        initial_user_turn_text="Help me think about coffee futures.",
        preferred_language_code="en",
        connect_to_database=_ConnectFactory([connection]),
        check_content_policy=lambda **_kwargs: {
            "provider_name": "google_gemini",
            "model_name": "gemini-test",
            "prompt_version": "policy-test",
            "analysis_mode": "test",
            "policy_check_status": "completed",
            "moderation_status": "allowed",
            "matched_prohibited_categories": [],
            "should_redact_original": False,
            "usage_metadata": {},
        },
        generate_ai_response=lambda **_kwargs: {
            "assistant_turn_text": "Here is a starting framework.",
            "provider_name": "google_gemini",
            "model_name": "gemini-test",
            "prompt_version": "chat-test",
            "prompt_fingerprint": "fingerprint",
            "google_search_enabled": False,
            "grounding_metadata": {},
            "usage_metadata": {},
        },
    )

    assert result["market_topic_id"] == 9001
    source_message_insert = next(
        statement
        for statement in connection.cursor_instance.executed_sql
        if "INSERT INTO stephen_dcx_contact_messages" in statement[0]
    )
    assert "'ready', 'completed', FALSE" in source_message_insert[0]
    assert any(
        "INSERT INTO stephen_dcx_market_topic_turns" in statement[0]
        for statement in connection.cursor_instance.executed_sql
    )


def test_blocks_direct_ai_chat_when_policy_check_is_prohibited() -> None:
    try:
        create_authenticated_dcx_user_ai_chat(
            authenticated_user_id=77,
            initial_user_turn_text="Synthetic prohibited message.",
            connect_to_database=_ConnectFactory([]),
            check_content_policy=lambda **_kwargs: {
                "moderation_status": "prohibited",
                "matched_prohibited_categories": ["prohibited_fraud"],
            },
            generate_ai_response=lambda **_kwargs: (_ for _ in ()).throw(AssertionError("AI should not run")),
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_DCX_AI_CHAT_PROHIBITED"
    else:
        raise AssertionError("Expected prohibited AI chat to raise")
