from django.shortcuts import render

from presentation.dependency_config import get_connection_repo, get_mapping_repo


def dashboard(request):
    connection_repo = get_connection_repo()
    mapping_repo = get_mapping_repo()
    connections = connection_repo.get_all()
    connections_with_mappings = []
    for conn in connections:
        mappings = mapping_repo.get_by_connection_id(conn.id)
        connections_with_mappings.append({"connection": conn, "mappings": mappings})
    return render(request, "dashboard.html", {"connections_with_mappings": connections_with_mappings})
