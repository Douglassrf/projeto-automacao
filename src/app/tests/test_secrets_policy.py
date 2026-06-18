from app.core.secrets_policy import SecretSeverity, SecretsPolicy, known_sensitive_keys


def test_secret_policy_masks_values_without_exposing_full_secret():
    policy = SecretsPolicy()

    assert policy.mask("abcd1234wxyz") == "abcd...wxyz"
    assert policy.mask("short") == "*****"


def test_secret_policy_warns_for_local_missing_secret_but_blocks_in_production():
    policy = SecretsPolicy()

    local = policy.check("META_ACCESS_TOKEN", "", production=False)
    prod = policy.check("META_ACCESS_TOKEN", "", production=True)

    assert local.severity == SecretSeverity.WARNING
    assert prod.severity == SecretSeverity.BLOCKED


def test_secret_policy_detects_weak_defaults():
    policy = SecretsPolicy()

    check = policy.check("JWT_SECRET_KEY", "change-me-local-dev-only", production=True)

    assert check.configured is True
    assert check.severity == SecretSeverity.BLOCKED
    assert check.masked_value == "chan...only"


def test_secret_policy_accepts_strong_secret_without_leaking_it():
    policy = SecretsPolicy()
    secret = "sk-live-1234567890abcdef-secret"

    check = policy.check("OPENAI_API_KEY", secret, production=True)

    assert check.severity == SecretSeverity.OK
    assert check.masked_value != secret
    assert check.masked_value.startswith("sk-l")


def test_secret_policy_audit_mapping_summarizes_status():
    policy = SecretsPolicy()

    result = policy.audit_mapping(
        {
            "JWT_SECRET_KEY": "change-me-local-dev-only",
            "META_ACCESS_TOKEN": "EAAB-valid-looking-token-123456",
            "APP_NAME": "AdIntelligence Pro",
        },
        production=True,
    )

    assert result["total"] == 3
    assert result["blocked"] == 1
    assert result["ok"] == 2
    assert result["safe_to_start_real_mode"] is False


def test_known_sensitive_keys_lists_core_tokens():
    keys = known_sensitive_keys()

    assert "META_ACCESS_TOKEN" in keys
    assert "JWT_SECRET_KEY" in keys
    assert "OPENAI_API_KEY" in keys
