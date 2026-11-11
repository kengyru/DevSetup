from rest_framework.routers import SimpleRouter

from .views import SetupViewSet

router = SimpleRouter()
router.register("setups", SetupViewSet, basename="setup")

urlpatterns = router.urls
