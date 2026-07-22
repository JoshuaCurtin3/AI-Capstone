"""Root URL configuration.

Keep this file thin: it only wires domain-app URLconfs together. Routing logic
belongs in each app's own urls.py; view/business logic belongs in views.py /
services.py, not here.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("app.api.urls")),
    path("accounts/", include("app.auth.urls")),
]
