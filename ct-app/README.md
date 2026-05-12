# ct-app

`ct-app` distributes wxHOPR through 1-hop messages in the Dufour network. In practice it
replaces the staking rewards users used to earn in the current staking season.

## Runtime

Install dependencies in a virtual environment:

```bash
pip install -r requirements.txt
```

Run the app with:

```sh
python -m core --configfile ./.configs/core_staging_config.yaml
```

### Environment

Parameter | Required | Notes
--|--|--
`HOPRD_API_HOST` | no | Defaults to `http://127.0.0.1:3001`
`HOPRD_API_TOKEN` | yes | Required startup secret
`BLOKLI_URL` | yes unless `blokli.url` is set in the config | Intended primary provider endpoint; use the GraphQL base URL (for example `http://localhost:8080` or `http://localhost:8080/graphql`)
`BLOKLI_TOKEN` | yes unless `blokli.token` is set in the config | Intended primary provider secret
`LOG_LEVEL` | no | Global or per-library log level overrides

`LOG_LEVEL` examples:

- `LOG_LEVEL=debug`
- `LOG_LEVEL=info,core.api=debug,mixins=warning`

### Config

The repo-owned config files live under `.configs/`. The parser shape is also reflected in
`test/test_config.yaml`.

For the legacy economic model, the supported behavior is fixed by the app and configured only
through:

- `economic_model.legacy.proportion`
- `economic_model.legacy.apr`
- `economic_model.legacy.coefficients.a`
- `economic_model.legacy.coefficients.b`
- `economic_model.legacy.coefficients.lowerbound`
- `economic_model.legacy.coefficients.upperbound`

There is no free-form formula language in the config anymore.


### Metrics

The metrics inventory is generated from the source code:

```bash
python scripts/generate_metrics_doc.py
```

The generated output is checked by the local pre-commit hook in `.pre-commit-config.yaml` and
written to [METRICS.md](./METRICS.md).

## Development Requirements

1. Any modern Linux distribution, e.g., Ubuntu >= 20.04.
    - If you are on Windows use [WSL](https://learn.microsoft.com/en-us/windows/wsl/install)
    - If you are on macOS (Intel/Apple Silicon) you are all fine

2. Docker for running software containers
Instructions for installation can be found [here](https://docs.docker.com/engine/install/ubuntu/#install-using-the-repository)
 *Notice: on macOS, simply install the [desktop client](https://docs.docker.com/desktop/install/mac-install/)*

3. Install Python >=3.9.10 and related packages
    - Ubuntu / WSL:
    ```
    $ sudo apt install python3 python3-pip
    ```
    - macOS: from the [official installer](https://www.python.org/downloads/) or using Homebrew:
    ```
    $ brew install python
    ```

4. Install the virtual environment manager:
```
$ pip3 install virtualenv
```

5. Visual Studio Code >= 1.78.2
To install it using `apt`:
```
$ sudo apt update
$ sudo apt install software-properties-common apt-transport-https wget
$ wget -q https://packages.microsoft.com/keys/microsoft.asc -O- | sudo apt-key add -
$ sudo add-apt-repository "deb [arch=amd64] https://packages.microsoft.com/repos/vscode stable main"
$ sudo apt update
$ sudo apt install code
```
Alternatively, download the `deb` package [here](https://code.visualstudio.com/sha/download?build=stable&os=linux-deb-x64) and install it manually.

***Notice:** On macOS, install it following these [instructions](https://code.visualstudio.com/docs/setup/mac)*

6. Formatting and linting: Black + Ruff combo is used.
Settings are found under `pyproject.toml`.
VSCode specific settings are found in `.vscode/settings.json`.
These should be automatically picked up by VSCode when using workspace settings.

7. Install [Black extension for VSCode](https://marketplace.visualstudio.com/items?itemName=ms-python.black-formatter)

8. Install [Ruff extension for VSCode](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff)

9. Clone, create virtual environment, install dependencies and launch VSCode:
```
$ git clone https://github.com/hoprnet/ct-research
$ cd ct-research/ct-app
$ python3 -m virtualenv /tmp/env
$ . /tmp/env/bin/activate
(env) $ pip install -r requirements_dev.txt
(...)
Successfully installed black-23.3.0 ...
(env) $ code .
```

10. Validate that everything is running correctly by launching the test cases. Its required to run a pluto cluster (see below) for the tests to pass. The test for `db_connection.py` are excluded as they require a local postgreSQL database. 
```
(env) $ pytest test
```

**Notice**: this last step requires that the local development cluster is running.

## Contact

- [Twitter](https://twitter.com/hoprnet)
- [Telegram](https://t.me/hoprnet)
- [Medium](https://medium.com/hoprnet)
- [Reddit](https://www.reddit.com/r/HOPR/)
- [Email](mailto:contact@hoprnet.org)
- [Discord](https://discord.gg/5FWSfq7)
- [Youtube](https://www.youtube.com/channel/UC2DzUtC90LXdW7TfT3igasA)

## License

[GPL v3](LICENSE) © HOPR Association
