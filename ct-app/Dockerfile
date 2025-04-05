# set base image (host OS)
FROM python:3.12
COPY --from=ghcr.io/astral-sh/uv:0.6.11 /uv /uvx /bin/

# set the working directory in the container
WORKDIR /code

# copy the current context to the working directory
COPY . .
RUN chmod +x ./scripts/run.sh

# update pip and install dependencies
RUN uv sync