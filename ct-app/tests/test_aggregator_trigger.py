import asyncio
import functools
from unittest.mock import MagicMock, patch

import pytest
import tools  # noqa: F401
import validators

from aggregator_trigger import AggregatorTrigger


def mock_decorator(*args, **kwargs):
    """Decorate by doing nothing."""

    def decorator(func):
        @functools.wraps(func)
        async def decorated_function(*args, **kwargs):
            return await func(*args, **kwargs)

        return decorated_function

    return decorator


# PATCH THE DECORATOR HERE
patch("tools.decorator.wakeupcall", mock_decorator).start()
patch("tools.decorator.formalin", mock_decorator).start()


def test_url_construction():
    """
    Test that the url is constructed correctly.
    """
    instance = AggregatorTrigger("http://gcp.host.com:5000/agg/send_list_to_db")

    assert validators.url(instance.endpoint_url)


def test_send_list_to_db():
    pass


@pytest.mark.asyncio
async def test_start(mocker):
    """
    Test whether all coroutines were called with the expected arguments.
    """
    mocker.patch.object(AggregatorTrigger, "send_list_to_db", return_value=None)

    instance = AggregatorTrigger("http://gcp.host.com:5000/agg/send_list_to_db")

    await instance.start()
    await asyncio.sleep(1)

    assert instance.send_list_to_db.called
    assert len(instance.tasks) == 1

    assert instance.started


def test_stop():
    """
    Test whether the stop method cancels the tasks and updates the 'started' attribute.
    """
    mocked_task = MagicMock()
    
    instance = AggregatorTrigger("http://gcp.host.com:5000/agg/send_list_to_db")
    instance.tasks = {mocked_task}

    instance.stop()

    assert not instance.started
    mocked_task.cancel.assert_called_once()
    assert instance.tasks == set()
