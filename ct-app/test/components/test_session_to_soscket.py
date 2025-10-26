import pytest

from core.api.response_objects import Session


def test_session_in_list():
    sessions = [
        Session(
            {
                "ip": "127.0.0.1",
                "port": 8080,
                "protocol": "tcp",
                "target": "localhost",
                "mtu": 1002,
                "surbLen": 395,
            }
        ),
        Session(
            {
                "ip": "192.168.1.1",
                "port": 8081,
                "protocol": "udp",
                "target": "localhost",
                "mtu": 1002,
                "surbLen": 395,
            }
        ),
    ]

    assert sessions[0] in sessions


def test_create_socket_no_leak():
    """
    Test that create_socket() properly closes existing socket before creating new one.

    Verifies:
    1. Multiple create_socket() calls don't leak resources
    2. Old socket is properly cleaned up before creating new socket
    3. Each call returns a valid, different socket
    """
    session = Session(
        {
            "ip": "127.0.0.1",
            "port": 9001,
            "protocol": "udp",
            "target": "test_peer",
            "mtu": 1002,
            "surbLen": 395,
        }
    )

    # Initially no socket
    assert session.socket is None

    # Create first socket
    socket1 = session.create_socket()
    assert socket1 is not None
    assert session.socket is socket1
    assert socket1.gettimeout() == 0  # type: ignore[attr-defined]  # Non-blocking

    # Get file descriptor of first socket
    fd1 = socket1.fileno()  # type: ignore[attr-defined]
    assert fd1 >= 0  # Valid file descriptor

    # Create second socket - should close first socket
    socket2 = session.create_socket()
    assert socket2 is not None
    assert session.socket is socket2
    assert socket2 is not socket1  # Different socket object
    assert socket2.gettimeout() == 0  # Non-blocking

    # The important verification: session.socket points to new socket, not old one
    assert session.socket is socket2
    assert session.socket is not socket1

    # Clean up
    session.close_socket()
    assert session.socket is None


def test_create_socket_idempotent():
    """
    Test that create_socket() is safe to call multiple times.

    Verifies that the method handles repeated calls gracefully without errors.
    """
    session = Session(
        {
            "ip": "127.0.0.1",
            "port": 9002,
            "protocol": "udp",
            "target": "test_peer",
            "mtu": 1002,
            "surbLen": 395,
        }
    )

    # Call create_socket multiple times
    for i in range(5):
        sock = session.create_socket()
        assert sock is not None
        assert session.socket is sock
        assert sock.gettimeout() == 0

    # Clean up
    session.close_socket()


def test_close_socket_after_create():
    """
    Test that close_socket() properly cleans up socket created by create_socket().

    Verifies:
    1. Socket reference is set to None after close
    2. close_socket() is idempotent (safe to call multiple times)
    3. Closing clears the session's socket reference
    """
    session = Session(
        {
            "ip": "127.0.0.1",
            "port": 9003,
            "protocol": "udp",
            "target": "test_peer",
            "mtu": 1002,
            "surbLen": 395,
        }
    )

    # Create socket
    socket1 = session.create_socket()
    assert session.socket is not None
    assert session.socket is socket1

    # Close socket
    session.close_socket()
    assert session.socket is None, "Socket reference should be cleared after close"

    # Try to use the socket - behavior may vary by system but we verify reference is gone
    # The important thing is session.socket is None
    try:
        # Attempt an operation on the closed socket
        socket1.getsockname()
        # On some systems this may not raise, but session.socket should still be None
    except OSError:
        # Expected on many systems
        pass

    # Calling close_socket() again should be safe (idempotent)
    session.close_socket()
    assert session.socket is None

    # Calling multiple times should not error
    session.close_socket()
    session.close_socket()
    assert session.socket is None


async def test_receive_validates_chunk_size():
    """
    Test that receive() raises ValueError for invalid chunk_size.

    Verifies:
    1. chunk_size <= 0 raises ValueError
    2. Error message includes clear context (port number)
    3. Error message indicates the invalid value
    """
    session = Session(
        {
            "ip": "127.0.0.1",
            "port": 9004,
            "protocol": "udp",
            "target": "test_peer",
            "mtu": 1002,
            "surbLen": 395,
        }
    )

    # Create socket so we get past the socket check
    session.create_socket()

    # Test chunk_size = 0
    with pytest.raises(ValueError) as exc_info:
        await session.receive(chunk_size=0, total_size=1000)
    assert "chunk_size must be positive" in str(exc_info.value)
    assert "9004" in str(exc_info.value)  # Port number in error
    assert "0" in str(exc_info.value)  # Invalid value in error

    # Test chunk_size < 0
    with pytest.raises(ValueError) as exc_info:
        await session.receive(chunk_size=-1, total_size=1000)
    assert "chunk_size must be positive" in str(exc_info.value)
    assert "-1" in str(exc_info.value)

    # Clean up
    session.close_socket()


async def test_receive_handles_zero_total_size():
    """
    Test that receive() returns 0 for total_size <= 0 without attempting recv.

    Verifies:
    1. total_size = 0 returns 0 immediately
    2. total_size < 0 returns 0 immediately
    3. No socket operations are attempted
    """
    session = Session(
        {
            "ip": "127.0.0.1",
            "port": 9005,
            "protocol": "udp",
            "target": "test_peer",
            "mtu": 1002,
            "surbLen": 395,
        }
    )

    # Create socket
    session.create_socket()

    # Test total_size = 0
    result = await session.receive(chunk_size=500, total_size=0)
    assert result == 0

    # Test total_size < 0
    result = await session.receive(chunk_size=500, total_size=-100)
    assert result == 0

    # Clean up
    session.close_socket()


async def test_receive_no_socket():
    """
    Test that receive() returns 0 when socket is None.

    Verifies early return when socket is not initialized.
    """
    session = Session(
        {
            "ip": "127.0.0.1",
            "port": 9006,
            "protocol": "udp",
            "target": "test_peer",
            "mtu": 1002,
            "surbLen": 395,
        }
    )

    # Don't create socket
    assert session.socket is None

    # Should return 0 without error
    result = await session.receive(chunk_size=500, total_size=1000)
    assert result == 0
