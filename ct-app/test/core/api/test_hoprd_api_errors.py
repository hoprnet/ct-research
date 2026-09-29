import logging
from unittest.mock import AsyncMock

import pytest
from api_lib.method import Method

from core.api.hoprd_api import HoprdAPI


@pytest.mark.asyncio
async def test_error_responses_are_logged_with_status_and_body(mocker, caplog):
    body = {"status": "NOT_FOUND", "error": "route not enabled"}
    mocker.patch("api_lib.ApiLib._call_api_with_timeout", new=AsyncMock(return_value=(404, body)))
    api = HoprdAPI("http://localhost:3001", None, "/api/v4")

    with caplog.at_level(logging.WARNING, logger="core.api.hoprd_api"):
        ok = await api.try_req(Method.POST, "/session/udp/explicit-path", return_state=True)

    assert ok is False
    record = next(r for r in caplog.records if r.getMessage() == "hoprd API returned an error")
    assert record.args["status"] == 404
    assert record.args["path"] == "/session/udp/explicit-path"
    assert "route not enabled" in record.args["body"]


@pytest.mark.asyncio
async def test_successful_responses_are_not_logged(mocker, caplog):
    mocker.patch(
        "api_lib.ApiLib._call_api_with_timeout", new=AsyncMock(return_value=(200, {"native": "0x"}))
    )
    api = HoprdAPI("http://localhost:3001", None, "/api/v4")

    with caplog.at_level(logging.WARNING, logger="core.api.hoprd_api"):
        await api.try_req(Method.GET, "/account/addresses")

    assert not [r for r in caplog.records if r.getMessage() == "hoprd API returned an error"]
