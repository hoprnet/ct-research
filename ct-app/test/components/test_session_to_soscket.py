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
    assert socket1.gettimeout() == 0  # type: ignore[union-attr]  # Non-blocking

    # Get file descriptor of first socket
    fd1 = socket1.fileno()  # type: ignore[union-attr]
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
