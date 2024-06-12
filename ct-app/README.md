# ct-app

This folder contains the ct-app.

The goal of the ct-app is to distribute wxHOPR token through 1 HOP messages in the Dufour network. The ct-app is responsible for replacing staking rewards users earn in the current staking season beyond its discontinuation.

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

## How to run the ct-app

### Requirements

To execute any of the modules you need to:

1. Setup a virtual environment

2. Install dependencies:
```bash
pip install -r requirements.txt
```


### Execute the app

To execute the module, create a bash script to specify a bunch of environment variables. The required parameters are the following:

Parameter | Recommanded value (staging)
--|--
`PGHOST` | (check Bitwarden)
`PGPORT` | `5432`
`PGUSER` | `ctdapp`
`PGPASSWORD` | (check Bitwarden)
`PGDATABASE` | `ctdapp` |
`SUBGRAPH_DEPLOYER_KEY` | (check Bitwarden)
`NODE_ADDRESS_X` (multiple, min. 2) | (check Bitwarden)
`NODE_KEY_X` | (check Bitwarden)

This program logs to STDOUT. The log level is set to INFO by default.

Then simply run 
```sh
python -m core --configfile ./scripts/core_staging_config.yaml
```

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
