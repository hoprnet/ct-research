# Cover Traffic dApp

This folder contains the cover traffic dApp.

The goal of the ct-dapp is to distribute cover traffic in the monte rosa network to keep the annoymity set of nodes sufficiently large at all times.

However, the fist version of the ct-dapp has the sole purpose of replacing the staking rewards users earn in the current staking season beyond its discontinuation.

## Development Requirements

1. Any modern Linux distribution, e.g., Ubuntu >= 20.04.
    - If you are on Windows use [WSL](https://learn.microsoft.com/en-us/windows/wsl/install)
    - If you are on macOS (Intel/Apple Silicon) you are all fine

2. Docker for running software containers
Instructions for installation can be found [here](https://docs.docker.com/engine/install/ubuntu/#install-using-the-repository)
 *Notice: on macOS, simply isntall the desktop client from [here](https://docs.docker.com/desktop/install/mac-install/)*

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
$ cd ct-research/ct-dApp
$ python3 -m virtualenv /tmp/env
$ . /tmp/env/bin/activate
(env) $ pip install -r requirements_dev.txt
(...)
Successfully installed black-23.3.0 ...
(env) $ code .
```

10. Validate that everything is running correctly by launching the test cases
```
(env) $ pytest 
```

## How to install and run a local development cluster on Ubuntu

HOPR uses a local development cluster called `Pluto` which allows you to interact with a fully interconnected cluster of HOPR nodes on your local machine.

1. Install HOPR Admin (optional). HOPR Admin is a visual interface of a HOPR node that can be used to visualize each node in your local cluster.
```bash
sudo docker run -d --name hopr_admin -p 3000:3000 gcr.io/hoprassociation/hopr-admin
```

2. Start docker:
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

## How to run the ct-dapp in the local development cluster

### Requirements

To execute the script called "ct.py" you need to:

1. Setup a virtual environment

2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Adapt the values in `run.sh` file:
```bash
#!/bin/sh

export HOPR_NODE_1='127.0.0.1'
export HOPR_NODE_1_HTTP_URL="http://${HOPR_NODE_1}:13305"
export HOPR_NODE_1_WS_URL="ws://${HOPR_NODE_1}:13305"
export HOPR_NODE_1_API_KEY='%th1s-IS-a-S3CR3T-ap1-PUSHING-b1ts-TO-you%'

python ct.py
```

### Configuration of Environment Variables
This program requires two environment variables to be set. If either of these environment variables is not set, the program will exit with an error.

1. `API_URL`: The URL of the API endpoint to be used. This variable is already set for you in the run.sh file above.
2. `API_TOKEN`: The authentication token to be used with the API endpoint. The authentication token is already set for you in the run.sh file above.


### Execute the Program

To execute the program, run the following command:

```bash
./run.sh
```

The program will execute the ct-dapp.

### Logging
This program logs to the file ct.log. The log level is set to INFO by default.

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
