import asyncio
import json
import requests


def send_req(method: str, url: str, headers: dict[str, str], payload: dict[str, str]) -> requests.Response:
    """
    Connects to 'url' using 'method' (either GET or POST).
    Optionally attaches 'header' and 'payload' as JSON data to the request.

    :returns: the response object, or throws an exception if failed.
    """
    if payload:
        data_payload = json.dumps(payload)
    else:
        data_payload = None
    response = requests.request(method,
                                url,
                                headers=headers,
                                data=data_payload,
                                timeout=30)
    return response


async def send_async_req(method: str, url: str, headers: dict[str, str], payload: dict[str, str]) -> requests.Response:
    """
    Asynchronously connects to 'url' using 'method' (either GET or POST).
    Optionally attaches 'header' and 'payload' as JSON data to the request.

    :returns: the response object, or throws an exception if failed.
    """
    return await asyncio.to_thread(send_req, method, url, headers, payload)
    