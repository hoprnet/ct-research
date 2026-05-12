from core.blokli.entries import BlokliRedemptionStats
from core.blokli.providers import Redemptions, TicketParametersSubscription


def test_subscription_query_uses_explicit_subscription_document_when_provided():
    provider = TicketParametersSubscription("http://blokli.local")

    assert provider._sku_subscription.startswith("subscription")
    assert "ticketParametersUpdated" in provider._sku_subscription


def test_parse_sse_event_data_returns_payload_dict():
    provider = Redemptions("http://blokli.local")
    payload = (
        '{"data":{"redeemedStats":{"nodeAddress":"0xnode","safeAddress":"0xsafe",'
        '"redeemedAmount":"3 wxHOPR","redemptionCount":2}}}'
    )

    parsed = provider._parse_sse_event_data(["event: next", f"data: {payload}"])

    assert parsed is not None
    assert parsed["redeemedStats"]["nodeAddress"] == "0xnode"
    assert parsed["redeemedStats"]["safeAddress"] == "0xsafe"


def test_parse_sse_event_data_returns_none_for_invalid_json():
    provider = Redemptions("http://blokli.local")

    parsed = provider._parse_sse_event_data(["data: {invalid-json"])

    assert parsed is None


def test_subscription_payload_is_converted_to_typed_response():
    provider = Redemptions("http://blokli.local")
    response = {
        "redeemedStats": {
            "nodeAddress": "0xnode",
            "safeAddress": "0xsafe",
            "redeemedAmount": "5 wxHOPR",
            "redemptionCount": 1,
        }
    }

    converted = provider._convert_response(response)

    assert isinstance(converted, BlokliRedemptionStats)
    assert converted.node_address == "0xnode"
    assert converted.safe_address == "0xsafe"


def test_request_headers_do_not_include_authorization_when_token_empty():
    provider = Redemptions("http://blokli.local", token="")

    headers = provider._request_headers()

    assert "Authorization" not in headers


def test_request_headers_include_authorization_when_token_present():
    provider = Redemptions("http://blokli.local", token="secret")

    headers = provider._request_headers()

    assert headers["Authorization"] == "Bearer secret"


def test_provider_normalizes_root_url_to_graphql_path():
    assert Redemptions("http://blokli.local").url == "http://blokli.local/graphql"
    assert Redemptions("http://blokli.local/graphql").url == "http://blokli.local/graphql"
