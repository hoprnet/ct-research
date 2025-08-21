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
