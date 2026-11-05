from collections import deque
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import pytest_socket
from aiohttp import web


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    yield


@pytest.hookimpl(trylast=True)
def pytest_runtest_setup():
    pytest_socket.socket_allow_hosts(["127.0.0.1"], allow_unix_socket=True)


@pytest.fixture
async def http(aiohttp_server, socket_enabled):
    # Permit loopback server creation, but still reject all external connects.
    pytest_socket.socket_allow_hosts(["127.0.0.1"], allow_unix_socket=True)
    replies = deque()
    requests = []

    async def handler(request):
        requests.append(
            (
                request.method,
                request.path,
                dict(request.query),
                await request.json() if request.can_read_body else None,
            )
        )
        method, payload, status, headers = replies.popleft()
        assert request.method == method
        assert (request.method, request.path) in {
            ("GET", "/api/v1/store/search"),
            ("POST", "/api/v1/store/metadata"),
        }
        if callable(payload):
            payload = await payload()
        if isinstance(payload, web.StreamResponse):
            return payload
        return web.json_response(payload, status=status, headers=headers)

    app = web.Application()
    app.router.add_route("*", "/api/v1/store/{tail:.*}", handler)
    server = await aiohttp_server(app, host="127.0.0.1", access_log=None)
    base = str(server.make_url("/api/v1/store"))

    def add(method, url=None, *, payload=None, status=200, headers=None, **kwargs):
        replies.append((method, payload, status, headers))

    with patch("custom_components.sportclips.client.BASE", base):
        yield SimpleNamespace(
            get=lambda *a, **k: add("GET", *a, **k),
            post=lambda *a, **k: add("POST", *a, **k),
            requests=requests,
            replies=replies,
        )
