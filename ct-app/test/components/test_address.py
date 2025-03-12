from core.components.address import Address


def test_equal_addresses():
    address1 = Address("hopr_address", "native_address")
    address2 = Address("hopr_address", "native_address")
    address3 = Address("h0pr_address", "native_address")
    address4 = Address("hopr_address", "nativ3_address")

    assert address1 == address2
    assert address1 != address3
    assert address1 != address4


def test_address_in():
    address1 = Address("hopr_address", "native_address")
    address2 = Address("hopr_address", "native_address")
    address3 = Address("h0pr_address", "native_address")
    address4 = Address("hopr_address", "nativ3_address")

    addresses = [address1, address2, address3]

    assert address1 in addresses
    assert address2 in addresses
    assert address3 in addresses
    assert address4 not in addresses
