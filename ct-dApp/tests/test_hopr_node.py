from hopr_node import HoprNode

key = 'something'
url = "some_url"
end_point = "/account/addresses"

def test_req():
    node = HoprNode(url, key)  # Create an instance of the HoprNode class
    request = node._req(end_point=end_point, method='GET', payload=None) 
    assert request.target_url == "{}/api/v2{}".format(url, end_point)