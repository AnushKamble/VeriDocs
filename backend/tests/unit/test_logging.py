from veridocs.utils.logging import (
    correlation_id_ctx,
    logger,
    redact_secrets,
    setup_logger,
)


def test_secret_redaction():
    text_with_key = "Connecting with api_key=sk-secret123456 to service"
    redacted = redact_secrets(text_with_key)
    assert "sk-secret123456" not in redacted
    assert "***REDACTED***" in redacted

    text_with_bearer = "Authorization: Bearer my_secret_token_val"
    redacted_bearer = redact_secrets(text_with_bearer)
    assert "my_secret_token_val" not in redacted_bearer


def test_correlation_id_context():
    token = correlation_id_ctx.set("corr-test-999")
    try:
        assert correlation_id_ctx.get() == "corr-test-999"
    finally:
        correlation_id_ctx.reset(token)
    assert correlation_id_ctx.get() is None
