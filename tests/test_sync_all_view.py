from types import SimpleNamespace

from django.test import Client

from presentation.views import import_api


class SyncAllUseCaseStub:
    def execute(self, start_date=None):
        return SimpleNamespace(results=[])


def test_sync_all_allows_internal_post_without_csrf(monkeypatch):
    monkeypatch.setattr(import_api, "get_sync_all_use_case", lambda: SyncAllUseCaseStub())

    client = Client(enforce_csrf_checks=True)
    response = client.post("/internal/api/imports/sync-all/")

    assert response.status_code == 200
    assert response.json() == {"results": []}


def test_sync_all_public_route_is_unavailable():
    client = Client(enforce_csrf_checks=True)

    response = client.post("/api/imports/sync-all/")

    assert response.status_code == 404
