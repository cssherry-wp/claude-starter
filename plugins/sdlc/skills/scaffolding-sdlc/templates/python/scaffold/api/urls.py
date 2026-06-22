from rest_framework.routers import DefaultRouter

from .views import WidgetViewSet

router = DefaultRouter()
router.register("widgets", WidgetViewSet, basename="widget")

urlpatterns = router.urls
