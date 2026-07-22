from django.apps import AppConfig


class EmailParserConfig(AppConfig):
    """Config for the email ingestion/parsing app.

    Responsible for turning raw email input (headers, body, attachments)
    into normalized, structured data for phishing_detection to score.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "app.email_parser"
