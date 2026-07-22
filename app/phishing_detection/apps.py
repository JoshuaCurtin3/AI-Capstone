from django.apps import AppConfig


class PhishingDetectionConfig(AppConfig):
    """Config for the deterministic phishing risk-scoring app.

    This is the single source of truth for the numerical risk score. It must
    remain pure and deterministic — no calls to an LLM or any non-deterministic
    input may influence the score (see CLAUDE.md).
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "app.phishing_detection"
