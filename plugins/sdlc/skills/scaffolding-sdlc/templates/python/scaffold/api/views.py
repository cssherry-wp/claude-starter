from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from .models import Widget
from .serializers import WidgetSerializer


class WidgetViewSet(viewsets.ModelViewSet):
    queryset = Widget.objects.all()
    serializer_class = WidgetSerializer
    # Example resource is intentionally public so the starter is demoable.
    # Real resources inherit the IsAuthenticated default from settings.
    permission_classes = [AllowAny]
