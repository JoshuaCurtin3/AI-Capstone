from django.apps import AppConfig


class AiAnalysisConfig(AppConfig):
    """Config for the Claude API explanation-generation app.

    This app only produces human-readable text describing an already-computed
    score. It must never compute, adjust, or override the numerical risk
    score produced by app.phishing_detection (see CLAUDE.md).
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "app.ai_analysis"
