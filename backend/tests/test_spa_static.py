from app.core.spa_static import SPAStaticFiles
from fastapi import FastAPI

from tests.asgi_client import ASGITestClient


def test_spa_static_files_falls_back_to_index_without_masking_api_404(tmp_path) -> None:
    (tmp_path / "index.html").write_text("<h1>Simulator shell</h1>", encoding="utf-8")
    app = FastAPI()
    app.mount("/", SPAStaticFiles(directory=tmp_path, html=True))

    with ASGITestClient(app) as client:
        client_route = client.get("/simulations/example/preview")
        assert client_route.status_code == 200
        assert "Simulator shell" in client_route.text

        api_route = client.get("/api/v1/not-a-route")
        assert api_route.status_code == 404
        assert "Simulator shell" not in api_route.text
