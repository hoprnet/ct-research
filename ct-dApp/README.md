# Cover Traffic dApp

This folder contains the cover traffic dApp.

The goal of the ct-dapp is to distribute cover traffic in the monte rosa network to keep the annoymity set of nodes sufficiently large at all times.

However, the fist version of the ct-dapp has the sole purpose to replace the staking rewards users earn in the current staking season beyond its discontinuation.

## Development Requirements

1. [Install Docker](https://docs.docker.com/engine/install/ubuntu/#install-using-the-repository)

2. Install python >=3.9.10

3. Visual Studio Code >= 1.78.2

4. Ubuntu >= 20.04 (if windows use WSL)

5. Linting: We use ruff >= v0.0.270 (to be implemented)

6. Code formating: We use  black (to be implemented)

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
3. Set up a run.sh file:
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
