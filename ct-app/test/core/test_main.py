from types import SimpleNamespace

import core.__main__ as app_main


class DummySection:
    def __init__(self, **attrs):
        self.calls: list[tuple[str, str]] = []
        for key, value in attrs.items():
            setattr(self, key, value)

    def set_attribute_from_env(self, attr: str, env_name: str) -> None:
        self.calls.append((attr, env_name))


class DummyNode:
    def __init__(self, host: str, token: str, params):
        self.host = host
        self.token = token
        self.params = params

    async def start(self):
        return None

    async def stop(self):
        return None


def build_dummy_params(host_url: str = "http://example:3001", host_token: str = "config-token"):
    return SimpleNamespace(
        blokli=DummySection(url="http://blokli.local", token="config-token"),
        host=DummySection(url=host_url, token=host_token),
    )


def test_main_wires_config_env_and_run_loop(tmp_path, monkeypatch, mocker):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("environment: test\n", encoding="utf-8")

    params = build_dummy_params(host_url="http://example:3001", host_token="secret-token")
    async_loop_run = mocker.patch.object(app_main.AsyncLoop, "run")
    start_http_server = mocker.patch.object(app_main, "start_http_server")
    node_factory = mocker.patch.object(app_main, "Node", side_effect=DummyNode)
    mocker.patch.object(app_main, "Parameters", return_value=params)

    monkeypatch.setenv("BLOKLI_URL", "http://blokli.example")
    monkeypatch.setenv("BLOKLI_TOKEN", "blokli-secret")

    app_main.main.callback(str(config_path))

    start_http_server.assert_called_once_with(8081)
    node_factory.assert_called_once_with("http://example:3001", "secret-token", params)
    start_callback, stop_callback = async_loop_run.call_args.args
    assert start_callback.__self__.host == "http://example:3001"
    assert start_callback.__self__.token == "secret-token"
    assert stop_callback.__self__ is start_callback.__self__


def test_main_continues_when_prometheus_start_fails(tmp_path, monkeypatch, mocker):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("environment: test\n", encoding="utf-8")

    params = build_dummy_params(host_url="", host_token="secret-token")
    async_loop_run = mocker.patch.object(app_main.AsyncLoop, "run")
    mocker.patch.object(app_main, "start_http_server", side_effect=OSError(48, "busy"))
    node_factory = mocker.patch.object(app_main, "Node", side_effect=DummyNode)
    mocker.patch.object(app_main, "Parameters", return_value=params)

    monkeypatch.setenv("BLOKLI_URL", "http://blokli.example")
    monkeypatch.setenv("BLOKLI_TOKEN", "blokli-secret")

    app_main.main.callback(str(config_path))

    node_factory.assert_called_once_with("", "secret-token", params)
    start_callback, stop_callback = async_loop_run.call_args.args
    assert start_callback.__self__.host == ""
    assert start_callback.__self__.token == "secret-token"
    assert stop_callback.__self__ is start_callback.__self__


def test_main_allows_empty_hoprd_api_token(tmp_path, monkeypatch, mocker):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("environment: test\n", encoding="utf-8")

    params = build_dummy_params(host_url="http://example:3001", host_token="")
    async_loop_run = mocker.patch.object(app_main.AsyncLoop, "run")
    node_factory = mocker.patch.object(app_main, "Node", side_effect=DummyNode)
    mocker.patch.object(app_main, "Parameters", return_value=params)
    mocker.patch.object(app_main, "start_http_server")

    monkeypatch.setenv("BLOKLI_URL", "http://blokli.example")
    monkeypatch.setenv("BLOKLI_TOKEN", "blokli-secret")

    app_main.main.callback(str(config_path))
    node_factory.assert_called_once_with("http://example:3001", "", params)
    assert async_loop_run.called


def test_main_allows_empty_blokli_url(tmp_path, monkeypatch, mocker):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("environment: test\n", encoding="utf-8")

    params = SimpleNamespace(
        blokli=DummySection(url="", token=""),
        host=DummySection(url="http://example:3001", token="secret-token"),
    )
    async_loop_run = mocker.patch.object(app_main.AsyncLoop, "run")
    node_factory = mocker.patch.object(app_main, "Node", side_effect=DummyNode)
    mocker.patch.object(app_main, "Parameters", return_value=params)
    mocker.patch.object(app_main, "start_http_server")

    monkeypatch.delenv("BLOKLI_URL", raising=False)
    monkeypatch.delenv("BLOKLI_TOKEN", raising=False)

    app_main.main.callback(str(config_path))
    node_factory.assert_called_once_with("http://example:3001", "secret-token", params)
    assert async_loop_run.called


def test_main_allows_empty_blokli_token(tmp_path, monkeypatch, mocker):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("environment: test\n", encoding="utf-8")

    params = SimpleNamespace(
        blokli=DummySection(url="http://blokli.example", token=""),
        host=DummySection(url="http://example:3001", token="secret-token"),
    )
    async_loop_run = mocker.patch.object(app_main.AsyncLoop, "run")
    mocker.patch.object(app_main, "start_http_server")
    node_factory = mocker.patch.object(app_main, "Node", side_effect=DummyNode)
    mocker.patch.object(app_main, "Parameters", return_value=params)

    monkeypatch.setenv("BLOKLI_URL", "http://blokli.example")
    monkeypatch.delenv("BLOKLI_TOKEN", raising=False)

    app_main.main.callback(str(config_path))

    node_factory.assert_called_once()
    assert async_loop_run.called
