import asyncio
import socket
import threading

import pytest
import uvicorn
from async_asgi_testclient import TestClient

from sowba_gateway.gateway import GatewayApp
from sowba_gateway.settings import Downstream, Settings

from .testservices import products, reviews, users

pytestmark = pytest.mark.asyncio


def get_open_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    s.listen(1)
    port = s.getsockname()[1]
    s.close()
    return port


class TestHTTPServer(threading.Thread):
    def __init__(self, app):
        self.app = app
        self.port = get_open_port()
        self._shutdown = threading.Event()

        super().__init__()

    def shutdown(self):
        self._shutdown.set()

    def run(self):
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self._run())

    async def _run(self):
        api_server = uvicorn.Server(
            config=uvicorn.Config(self.app, port=self.port, host="localhost")
        )
        task = asyncio.create_task(api_server.serve())
        while True:
            await asyncio.sleep(0.1)
            if self._shutdown.isSet():
                api_server.should_exit = True
                await api_server.shutdown()
                await asyncio.wait([task])
                return


@pytest.fixture(scope="session")
def test_services():
    user_service = TestHTTPServer(users.app)
    user_service.start()

    products_service = TestHTTPServer(products.app)
    products_service.start()

    reviews_service = TestHTTPServer(reviews.app)
    reviews_service.start()

    yield [
        Downstream(
            base_url=f"http://localhost:{user_service.port}",
            openapi_url=f"http://localhost:{user_service.port}/openapi.json",
        ),
        Downstream(
            base_url=f"http://localhost:{products_service.port}",
            openapi_url=f"http://localhost:{products_service.port}/openapi.json",
        ),
        Downstream(
            base_url=f"http://localhost:{reviews_service.port}",
            openapi_url=f"http://localhost:{reviews_service.port}/openapi.json",
        ),
    ]

    user_service.shutdown()
    products_service.shutdown()
    reviews_service.shutdown()

    user_service.join()
    products_service.join()
    reviews_service.join()


@pytest.fixture()
async def gateway_client(test_services):
    app = GatewayApp(Settings(services=test_services))
    await asyncio.sleep(0.2)
    async with TestClient(app) as client:
        yield client


async def test_gateway_merge_results(gateway_client):
    resp = await gateway_client.get("/users/1")
    data = resp.json()
    assert resp.status_code == 200, data
    assert data == {
        "id": "1",
        "name": "Isaac Newton",
        "reviews": [{"body": "Great!", "product": {"id": "1", "name": "Principia Mathematica"}}],
    }


async def test_get_merged_open_api(gateway_client):
    resp = await gateway_client.get("/openapi.json")
    data = resp.json()

    assert resp.status_code == 200, data
    assert "/products/{id}" in data["paths"]
    assert "reviews" in data["components"]["schemas"]["User"]["properties"]


async def test_docs(gateway_client):
    resp = await gateway_client.get("/docs")
    assert resp.status_code == 200

    resp = await gateway_client.get("/redoc")
    assert resp.status_code == 200
