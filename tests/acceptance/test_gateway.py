import asyncio
import contextlib
import socket

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


@contextlib.asynccontextmanager
async def http_server(app):
    port = get_open_port()
    api_server = uvicorn.Server(config=uvicorn.Config(app, port=port, host="localhost"))
    task = asyncio.create_task(api_server.serve())
    yield port
    api_server.should_exit = True
    await api_server.shutdown()
    await asyncio.wait([task])


@pytest.fixture()
async def gateway_client():
    async with http_server(users.app) as users_port, http_server(
        products.app
    ) as products_port, http_server(reviews.app) as reviews_port:
        app = GatewayApp(
            Settings(
                services=[
                    Downstream(
                        base_url=f"http://localhost:{users_port}",
                        openapi_url=f"http://localhost:{users_port}/openapi.json",
                    ),
                    Downstream(
                        base_url=f"http://localhost:{products_port}",
                        openapi_url=f"http://localhost:{products_port}/openapi.json",
                    ),
                    Downstream(
                        base_url=f"http://localhost:{reviews_port}",
                        openapi_url=f"http://localhost:{reviews_port}/openapi.json",
                    ),
                ]
            )
        )
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
