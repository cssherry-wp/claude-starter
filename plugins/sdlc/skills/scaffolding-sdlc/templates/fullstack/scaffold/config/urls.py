from django.urls import include, path, re_path
from django.views.generic import TemplateView

urlpatterns = [
    path("api/", include("api.urls")),
    # SPA fallback: serve the built index.html for all non-API routes so
    # client-side routing works. Resolves only when frontend/dist is present
    # (i.e. in the container); harmless in local dev/tests.
    re_path(r"^(?!api/).*$", TemplateView.as_view(template_name="index.html")),
]
