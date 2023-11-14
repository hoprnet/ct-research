from aggregator_trigger import AggregatorTrigger
import validators


def test_url_construction():
    """
    Test that the url is constructed correctly.
    """
    instance = AggregatorTrigger("http://gcp.host.com:5000/")

    assert validators.url(instance.endpoint)


# the send_list_to_db() method is not tested here, but the accessed endpoint is tested
# in the aggregator unit tests.
# The stop() and start() method are not tested here, as there is only one method that is
# called in the start() method, and the stop() method is only used to stop this task.
