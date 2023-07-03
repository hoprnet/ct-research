from aggregator import Aggregator

agg = Aggregator()


def clear_instance(func):
    def wrapper(*args, **kwargs):
        agg = Aggregator()
        agg._dict = {}
        agg._update_dict = {}
        
        func(*args, **kwargs)
    return wrapper

@clear_instance
def test_singleton():
    """
    Test that the aggregator is implemented as a singleton.
    """
    agg1 = Aggregator()
    agg2 = Aggregator()

    assert agg1 is agg2

@clear_instance
def test_singleton_update():
    """
    Test that when an instance of the aggregator is updated, all the other instances 
    are updated as well.
    """
    agg1 = Aggregator()
    agg2 = Aggregator()

    agg1.add("pod_id", {"peer": 1})
    agg2.set_update("pod_id", "timestamp")

    assert agg1.get() == agg2.get()

@clear_instance
def test_add():
    """
    Test that the add method works correctly.
    """
    pod_id = "pod_id"
    items = {"peer": 1}

    agg.add(pod_id, items)

    assert agg._dict.get(pod_id) == items

@clear_instance
def test_get():
    """
    Test that the get method works correctly.
    """
    pod_id = "pod_id"
    items = {"peer": 1}

    agg._dict[pod_id] = items

    assert agg.get() == {pod_id: items}

@clear_instance
def test_clear():
    """
    Test that the clear method works correctly.
    """
    pod_id = "pod_id"
    items = {"peer": 1}

    agg.add(pod_id, items)

    agg.clear()

    assert agg._dict == {}

@clear_instance
def test_set_update():
    """
    Test that the set_update method works correctly.
    """
    pod_id = "pod_id"
    timestamp = "timestamp"

    agg.set_update(pod_id, timestamp)

    assert agg._update_dict.get(pod_id) == timestamp

@clear_instance
def test_get_update():
    """
    Test that the get_update method works correctly.
    """
    pod_id = "pod_id"
    timestamp = "timestamp"

    agg._update_dict[pod_id] = timestamp

    assert agg.get_update(pod_id) == timestamp

@clear_instance
def test_get_update_not_in_dict():
    """
    Test that the get_update method works correctly when the pod_id is not in the dict.
    """
    pod_id = "pod_id"

    assert not agg.get_update(pod_id)
    
@clear_instance
def test_get_metric():
    """
    Test that the get_metric method works correctly.
    """
    assert isinstance(agg.get_metrics(), dict)

@clear_instance
def test_convert_to_db_data_simple():
    """
    Test that the convert_to_db_data method works correctly.
    """
    pod_id = "pod_id"
    items = {"peer": 1}

    agg.add(pod_id, items)

    assert agg.convert_to_db_data() == [("peer", ["pod_id"], [1])]


@clear_instance
def test_add_multiple():
    """
    Test that the add method works correctly when adding multiple items.
    """
    pod_id = "pod_id"
    items = {"peer": 1, "peer2": 2}

    agg.add(pod_id, items)

    assert agg.get()[pod_id] == items

@clear_instance
def test_add_multiple_pods():
    """
    Test that the add method works correctly when adding multiple pods.
    """
    pod_id = "pod_id"
    pod_id2 = "pod_id2"
    items = {"peer": 1}
    items2 = {"peer2": 2}

    agg.add(pod_id, items)
    agg.add(pod_id2, items2)

    assert agg.get()[pod_id] == items
    assert agg.get()[pod_id2] == items2

@clear_instance
def test_add_to_existing_pod():
    """
    Test that the add method works correctly when adding to an existing pod.
    """
    pod_id = "pod_id"
    items = {"peer": 1}
    items2 = {"peer2": 2}

    agg.add(pod_id, items)
    agg.add(pod_id, items2)

    print(agg.get())
    assert agg.get()[pod_id] == {"peer": 1, "peer2": 2} 

@clear_instance
def test_add_to_existing_pod_multiple():
    """
    Test that the add method works correctly when adding multiple items to an existing 
    pod.
    """
    pod_id = "pod_id"
    items = {"peer": 1}
    items2 = {"peer": 2, "peer2": 1}
    items3 = {"peer2": 2}

    agg.add(pod_id, items)
    agg.add(pod_id, items2)
    agg.add(pod_id, items3)

    assert agg.get()[pod_id] == {"peer": 2, "peer2": 2}

# Finally managed to run unittests by moving app.run statement to main block

# # tiny app server starts here
# app = Sanic(__name__)
# generate_crud(app, [Metrics, ...])
# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=1337, debug=True)
#         # workers=4, log_config=LOGGING)
# and

# from restapi import app
# import json
# import unittest

# class AutoRestTests(unittest.TestCase):
#     ''' Unit testcases for REST APIs '''

#     def test_get_metrics_all(self):
#         request, response = app.test_client.get('/metrics')
#         self.assertEqual(response.status, 200)
#         data = json.loads(response.text)
#         self.assertEqual(data['metric_name'], 'vCPU')

# if __name__ == '__main__':
#     unittest.main()