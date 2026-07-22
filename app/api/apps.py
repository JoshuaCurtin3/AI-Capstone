from django.apps import AppConfig


class ApiConfig(AppConfig):
    """Config for the HTTP API app.

    This app is intentionally thin: routing and (de)serialization only. All
    business logic is delegated to each domain's services.py.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "app.api"
