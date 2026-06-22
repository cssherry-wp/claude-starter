import pytest
from rest_framework.test import APIClient

from api.models import Widget


@pytest.mark.django_db
def test_create_and_list_widget():
    client = APIClient()

    create = client.post("/api/widgets/", {"name": "gadget"}, format="json")
    assert create.status_code == 201
    assert create.data["name"] == "gadget"

    listing = client.get("/api/widgets/")
    assert listing.status_code == 200
    assert len(listing.data) == 1
    assert Widget.objects.count() == 1
