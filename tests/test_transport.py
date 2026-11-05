import socket
from datetime import timedelta

import aiohttp
import pytest
import pytest_socket

from custom_components.sportclips.client import (
    ProviderError,
    RequestGate,
    SportClipsClient,
)


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
async def test_errors_back_off_and_sanitize(http, freezer, status):
    http.get(
        status=status, payload={"secret": "CANARY"}, headers={"Retry-After": "600"}
    )
    http.get(payload={"response": {"searchedLocations": []}})
    gate = RequestGate()
    async with aiohttp.ClientSession() as session:
        client = SportClipsClient(session, gate)
        with pytest.raises(ProviderError) as error:
            await client.search("Example")
        assert "CANARY" not in str(error.value)
        assert error.value.retry_after >= 600
        with pytest.raises(ProviderError):
            await SportClipsClient(session, gate).search("Example")
        assert len(http.requests) == 1
        freezer.tick(timedelta(seconds=601))
        assert await client.search("Example") == []
    assert len(http.requests) == 2


async def test_http_date_retry_after(http, freezer):
    freezer.move_to("2026-11-05T21:00:00Z")
    http.get(status=429, headers={"Retry-After": "Thu, 05 Nov 2026 21:10:00 GMT"})
    async with aiohttp.ClientSession() as session:
        with pytest.raises(ProviderError) as error:
            await SportClipsClient(session).search("Example")
    assert error.value.retry_after == 600


async def test_external_network_stays_blocked(http):
    with socket.socket() as connection:
        with pytest.raises(pytest_socket.SocketConnectBlockedError):
            connection.connect(("192.0.2.1", 443))


async def test_timeout_sanitized(http):
    from unittest.mock import patch

    async with aiohttp.ClientSession() as session:
        with patch.object(session, "request", side_effect=TimeoutError("CANARY")):
            with pytest.raises(ProviderError, match="transport"):
                await SportClipsClient(session).search("Example")


@pytest.mark.parametrize("header", ["invalid", "-5", "nan", "inf"])
async def test_malformed_retry_after_safe_floor(http, header):
    http.get(status=429, headers={"Retry-After": header})
    async with aiohttp.ClientSession() as session:
        with pytest.raises(ProviderError) as error:
            await SportClipsClient(session).search("Example")
    assert error.value.retry_after == 120


async def test_non_object_json_rejected(http):
    http.get(payload=[])
    async with aiohttp.ClientSession() as session:
        with pytest.raises(ProviderError, match="invalid_response"):
            await SportClipsClient(session).search("Example")


async def test_cancellation_propagates_without_becoming_provider_failure(http):
    import asyncio
    from unittest.mock import patch

    gate = RequestGate()
    async with aiohttp.ClientSession() as session:
        with patch.object(session, "request", side_effect=asyncio.CancelledError):
            with pytest.raises(asyncio.CancelledError):
                await SportClipsClient(session, gate).search("Example")
    assert gate.failures == 0


async def test_extreme_retry_after_does_not_crash_cooldown(http):
    http.get(status=429, headers={"Retry-After": "999999999999999999999999999"})
    async with aiohttp.ClientSession() as session:
        client = SportClipsClient(session)
        with pytest.raises(ProviderError):
            await client.search("Example")
        with pytest.raises(ProviderError, match="cooldown"):
            await client.search("Example")
    assert len(http.requests) == 1


async def test_invalid_json_is_sanitized(http):
    from aiohttp import web

    http.get(
        payload=web.Response(
            body=b"PRIVATE_INVALID_JSON", content_type="application/json"
        )
    )
    async with aiohttp.ClientSession() as session:
        with pytest.raises(ProviderError, match="invalid_response") as error:
            await SportClipsClient(session).search("Example")
    assert "PRIVATE_INVALID_JSON" not in str(error.value)


async def test_exponential_backoff_resets_after_recovery(http, freezer):
    gate = RequestGate()
    async with aiohttp.ClientSession() as session:
        client = SportClipsClient(session, gate)
        for delay in (120, 240, 480):
            http.get(status=503)
            with pytest.raises(ProviderError) as error:
                await client.search("Example")
            assert error.value.retry_after == delay
            freezer.tick(timedelta(seconds=delay + 1))
        http.get(payload={"response": {"searchedLocations": []}})
        assert await client.search("Example") == []
        http.get(status=500)
        with pytest.raises(ProviderError) as error:
            await client.search("Example")
        assert error.value.retry_after == 120
