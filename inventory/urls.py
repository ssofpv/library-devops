from rest_framework.routers import SimpleRouter

from .views import BranchViewSet, CopyViewSet

router = SimpleRouter()
router.register("branches", BranchViewSet, basename="branch")
router.register("copies", CopyViewSet, basename="copy")

urlpatterns = router.urls
