from core.components.address import Address


def test_equal_addresses():
    address1 = Address("native_address")
    address2 = Address("native_address")
    address3 = Address("nativ3_address")

    assert address1 == address2
    assert address1 != address3


def test_address_in():
    address1 = Address("native_address")
    address2 = Address("nativ2_address")
    address3 = Address("nativ3_address")

    addresses = [address1, address2]

    assert address1 in addresses
    assert address2 in addresses
    assert address3 not in addresses
