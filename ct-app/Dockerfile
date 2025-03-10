# set base image (host OS)
FROM python:3.9

# set the working directory in the container
WORKDIR /code

# copy the current context to the working directory
COPY . .
RUN chmod +x ./scripts/run.sh

# update pip and install dependencies
RUN pip install --upgrade --requirement requirements.txt