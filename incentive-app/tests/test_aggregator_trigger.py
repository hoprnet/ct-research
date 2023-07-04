from aggregator_trigger import AggregatorTrigger
import validators


def test_url_construction():
    """
    Test that the url is constructed correctly.
    """
    instance = AggregatorTrigger("gcp.host.com", 5000, "/agg/send_list_to_db")

    assert validators.url(instance.endpoint_url)


def test_good_request():
    assert False


def test_bad_request():
    assert False
