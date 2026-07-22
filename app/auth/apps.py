from django.apps import AppConfig


class AuthConfig(AppConfig):
    """Config for the LDAPS/Active Directory authentication app.

    label is set explicitly to "capstone_auth" because the default label
    derived from the app name ("auth") collides with Django's built-in
    django.contrib.auth app.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "app.auth"
    label = "capstone_auth"
