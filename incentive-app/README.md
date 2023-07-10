# Incentive App

This folder contains the incentive-app.

The goal of the incentive-app is to distribute wxHOPR token through 1 HOP messages in the monte rosa network. The incentive-app is responsible for replacing staking rewards users earn in the current staking season beyond its discontinuation.

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
$ cd ct-research/incentive-app
$ python3 -m virtualenv /tmp/env
$ . /tmp/env/bin/activate
(env) $ pip install -r requirements_dev.txt
(...)
Successfully installed black-23.3.0 ...
(env) $ code .
```

10. Validate that everything is running correctly by launching the test cases. Its required to run a pluto cluster (see below) for the tests to pass. The test for `db_connection.py` are excluded as they require a local postgreSQL database. 
```
(env) $ pytest -k "not db_connection.py"
```

**Notice**: this last step requires that the local development cluster is running.

## How to install and run a local development cluster on Ubuntu

HOPR uses a local development cluster called `Pluto` which allows you to interact with a fully interconnected cluster of HOPR nodes on your local machine.

1. Install HOPR Admin (optional). HOPR Admin is a visual interface of a HOPR node that can be used to visualize each node in your local cluster.
```bash
sudo docker run -d --name hopr_admin -p 3000:3000 gcr.io/hoprassociation/hopr-admin
```

2. Start docker:
```bash
sudo dockerd
```
If the docker serivice is not enabled run the following line beforehand.

```bash
sudo systemctl enable docker.service
```
***Notice:** This step is not necessary on macOS. Simply be sure that the Docker daemon is running by launching it from your Application folder*

3. Use a seperate terminal create your local cluster of HOPR nodes:
```bash
sudo docker run -ti -p 13301-13305:13301-13305  gcr.io/hoprassociation/hopr-pluto:1.93.7
```

4. Use a seperate terminal to start HOPR Admin (optional):
```bash
sudo docker start hopr_admin
```

## How to run the incentive-app in the local development cluster

### Requirements

To execute any of the modules you need to:

1. Setup a virtual environment

2. Install dependencies:
```bash
pip install -r requirements.txt
```

#### Comments
- ```python -m <module> --help``` provide a descrition of each parameter.
- The ```plot-folder``` is the place where all the generated plots are stored. It has a default value that is ```.```. It is highly recommended to specify a different folder. At runtime, the specified folder will be created if necessary.

### Configuration of Parameters
To run the individual modules of the app, each of them requires a different set of parameters to run. To check which parameters are required for each module, run the following command:

```python
python -m <module> --help
```

#### Aggregator
parameter | description
--- | ---
`--module`  | name of the module
`--host`    | host address for the web server
`--port`    | exposed port for the web server
`--db`      | name of the database to store metrics to
`--dbhost`  | host address of the database
`--dbuser`  | database connection username
`--dbpass`  | database connection password
`--dbport`  | database opened port

```bash
sh ./run.sh --module aggregator --host <host> --port <port> --db <dbname> --dbhost <dbhost> --dbuser <dbuser> --dbpass <dbpass> --dbport <dbport>
```

#### Aggregator Trigger
parameter | description
--- | ---
`--module`  | name of the module
`--host`    | host address of the aggregator
`--port`    | exposed port of the aggregator
`--route`   | route to trigger 
```bash
sh ./run.sh --module aggtrigger --host <host> --port <port> --route <route>
```

#### Economic Handler
parameter | description
--- | ---
`--module`     | name of the module
`--apihost`    | host address of the node to connect to
`--apiport`    | exposed port of the node to connect to
`--key`        | connection key for the node
`--rchpnodes`  | endpoint to retrieve the RCPh nodes IDs
```bash
sh ./run.sh --module economic_handler --apihost <apihost> --apikey <apikey> --port <port> --rcphnodes <rcphnodes>
```

#### Netwatcher
parameter | description
--- | ---
`--module`  | name of the module
`--host`    | host address of the node to connect to
`--port`    | exposed port of the node to connect to
`--key`     | connection key for the node
`--aggpost` | POST endpoint to call for transmitting the peer list
```bash
sh ./run.sh --module netwatcher --host <host> --port <port> --key <key> --aggpost <aggpost>
```

### Execute the Program

To execute the program, two methods are available:
- run the python module directly:
```python
python -m <module> [PARAMETERS]
```
- run the `run.sh` script:
```bash
./run.sh --module <module> --port 13301 --host "127.0.0.1" --key "%th1s-IS-a-S3CR3T-ap1-PUSHING-b1ts-TO-you%" --rcphendpoint "rpch_endpoint"
```

### Logging
This program logs to STDOUT. The log level is set to INFO by default.

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
