"""Root API routing. Version-specific routes live under v1/, v2/, etc."""

from django.urls import include, path

urlpatterns = [
    path("v1/", include("app.api.v1.urls")),
]
