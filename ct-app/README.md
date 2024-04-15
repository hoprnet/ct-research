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

## (Outdated) How to install and run a local development cluster on Ubuntu

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

## How to run the ct-app in the local development cluster

### Requirements

To execute any of the modules you need to:

1. Setup a virtual environment

2. Install dependencies:
```bash
pip install -r requirements.txt
```


### Execute the app

The app is splitted into 2 components: `ct-core` and `postman`.


#### ct-core
It is the heart of the app. Using multiple hoprd nodes, it observes the network, retrieve the peers connected, compute their rewards, and schedule the reward distribution.

To execute the module, create a bash script to specify a bunch of environment variables. The required parameters are the following:

Parameter | Recommanded value (staging) | Description
--|--|--
`CHANNEL_MIN_BALANCE` | `0.05` | Threshold to trigger channel funding 
`CHANNEL_FUNDING_AMOUNT` | `0.2` | Amount to fund a channel with
`CHANNEL_MAX_AGE_SECONDS` | `30` | If peer is not seen after this delay, its channel gets closed
`DISTRIBUTION_MAX_APR_PERCENTAGE` | `15` | APR upperbound 
`DISTRIBUTION_MIN_ELIGIBLE_PEERS` | `5` | Minimum number of eligible peers to distribute rewards
`ECONOMIC_MODEL_FILENAME` | `parameters-staging.json` | Name of parameter file on staging (in folder `./assets/`)
`ECONOMIC_MODEL_MIN_SAFE_ALLOWANCE` | `0.0001` | Minimum safe allowance to be eligible
`ECONOMIC_MODEL_NFT_THRESHOLD` | `30000` | Minimum stake if someone's not holding a NR-NFT
`GCP_BUCKET` | `ct-platform-ct` |
`GCP_FILE_PREFIX` | `expected_reward` | File prefix for GCP distribution list storage
`GCP_FOLDER` | `staging` | Folder on GCP where to store distribution list
`PEER_MIN_VERSION` | `2.0.0` | Minimum node version to be eligible
`RABBITMQ_HOST` | (check Bitwarden) | 
`RABBITMQ_PASSWORD` | (check Bitwarden) | 
`RABBITMQ_PROJECT_NAME` | `ct-app` | Name of the RabbitMQ project
`RABBITMQ_TASK_NAME` | `fake_task` | Task to create when distributing rewards
`RABBITMQ_USERNAME` | (check Bitwarden) | 
`RABBITMQ_VIRTUALHOST` | (check Bitwarden) | 
`SUBGRAPH_SAFES_BALANCE_URL` | (`hopr-nodes-dufour` decentralized subgraph) | 
`SUBGRAPH_SAFES_BALANCE_URL_BACKUP` | (`hopr-nodes-dufour` centralized subgraph) | 
`SUBGRAPH_STAKING_URL` | |
`SUBGRAPH_STAKING_URL_BACKUP` | |
`SUBGRAPH_WXHOPR_TXS_URL` | (`wxhoprtransactions` decentralized subgraph) | 
`SUBGRAPH_WXHOPR_TXS_URL_BACKUP` | (`wxhoprtransactions` centralized subgraph) | 
`NODE_ADDRESS_X` (multiple, min. 2) | (check Bitwarden) |
`NODE_KEY_X` | (check Bitwarden) | 


Then there's a bunch of optional flags to enable features of the app
Flag | Recommanded value (staging)
--|--
`FLAG_CORE_HEALTHCHECK` |--
`FLAG_CORE_CHECK_SUBGRAPH_URLS` |--
`FLAG_CORE_GET_FUNDINGS` |--
`FLAG_CORE_AGGREGATE_PEERS` |--
`FLAG_CORE_GET_TOPOLOGY_DATA` |--
`FLAG_CORE_GET_REGISTERED_NODES` |--
`FLAG_CORE_GET_NFT_HOLDERS` |--
`FLAG_CORE_APPLY_ECONOMIC_MODEL` |--
`FLAG_CORE_DISTRIBUTE_REWARDS` |--
`FLAG_NODE_HEALTHCHECK` |--
`FLAG_NODE_RETRIEVE_PEERS` |--
`FLAG_NODE_RETRIEVE_OUTGOING_CHANNELS` |--
`FLAG_NODE_RETRIEVE_INCOMING_CHANNELS` |--
`FLAG_NODE_RETRIEVE_BALANCES` |--
`FLAG_NODE_OPEN_CHANNELS` |--
`FLAG_NODE_CLOSE_OLD_CHANNELS` |--
`FLAG_NODE_CLOSE_PENDING_CHANNELS` |--
`FLAG_NODE_FUND_CHANNELS` |--
`FLAG_NODE_CLOSE_INCOMING_CHANNELS` (Not available) |--
`FLAG_NODE_GET_TOTAL_CHANNEL_FUNDS` |--

Those flags turn on the corresponding feature if the variable exist. Also, the value associated to the flag defines the delay between two executions of the methods.

#### postman
This module handles message distribution. It relies on a bunch of parameters:

Parameter | Recommanded value (staging) | Description
--|--|--
`PARAM_BATCH_SIZE` | `50` | Number of messages to send before checking the inbox
`PARAM_DELAY_BETWEEN_TWO_MESSAGES` | `0.25` | Delay between two messages
`PARAM_MAX_ATTEMPTS` | `4` | Maximum number of retries before timing out
`PARAM_MESSAGE_DELIVERY_TIMEOUT` | `10` | Delay between two batches

#### Common parameters
In addition to the above-mentioned parameters, there's a bunch of parameters that are required to be able to communicate with databases, RabbitMQ brokers, and nodes.
Parameter | Recommanded value (staging) | Description
--|--|--
`RABBITMQ_HOST` | (check Bitwarden) | 
`RABBITMQ_PASSWORD` | (check Bitwarden) | 
`RABBITMQ_PROJECT_NAME` | `ct-app` | Name of the RabbitMQ project
`RABBITMQ_TASK_NAME` | `fake_task` | Task to create when distributing rewards
`RABBITMQ_USERNAME` | (check Bitwarden) | 
`RABBITMQ_VIRTUALHOST` | (check Bitwarden) | 
`PGHOST` | (from gcloud) |
`PGPORT` | `5432` |
`PGUSER` | `ctdapp` |
`PGPASSWORD` | (from gcloud) |
`PGDATABASE` | `ctdapp` |
`PGSSLCERT` |  | Path to the SSL user certificate
`PGSSLKEY` |  | Path to the SSL user key
`PGSSLROOTCERT` |  | Path to the SSL root certificate
`PGSSLMODE` | `verify-ca` | 
`NODE_ADDRESS_X` (multiple, min. 2) | (check Bitwarden) | Node endpoints in the format `http://ip:port`
`NODE_KEY_X` (multiple, min. 2) | (check Bitwarden) | Node API token


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
