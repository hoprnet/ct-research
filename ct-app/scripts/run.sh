#!/bin/bash

export $(grep -v '^#' .env | xargs)

# Default values
env="local"
deployment="auto"
log_folder=".logs"

# Function for checking health
healthyz() { echo $(curl -s -o /dev/null -w "%{http_code}" "$1/healthyz"); }

# Function for checking deployment
check_deployment() {
    if [ $(healthyz $(printf $1 "blue" "1" $2)) -eq 200 ]; then
        echo "blue"
        exit 1
    elif [ $(healthyz $(printf $1 "green" "1" $2)) -eq 200 ]; then
        echo "green"
        exit 1
    fi
}


get_local_node_address() {
    port=$((3000 + $1 * 3))
    echo "http://localhost:$port"
}


# Parse command-line flags (long flags and short flags)
for arg in "$@"; do
    case $arg in
        --env=*)
            env="${arg#*=}"
            shift
            ;;
        --deployment=*)
            deployment="${arg#*=}"
            shift
            ;;
        --log-folder=*)
            log_folder="${arg#*=}"
            shift
            ;;
        -e*)
            env="${arg#*=}"
            shift
            ;;
        -d*)
            deployment="${arg#*=}"
            shift
            ;;
        -l*)
            log_folder="${arg#*=}"
            shift
            ;;
        *)
            # Invalid argument
            echo "Usage: $0 [--env=ENV] [--deployment=DEPLOYMENT] [--log-folder=LOG_FOLDER]"
            exit 1
            ;;
    esac
done

if [ $env == "local" ]; then
    export HOPRD_API_HOST=$(get_local_node_address 1)
    export HOPRD_API_TOKEN="e2e-API-token^^"

else
    # Check deployment if it's set to auto
    if [ $deployment == "auto" ]; then
        deployment=$(check_deployment $HOST_FORMAT $env)
    fi

    # Node parameters
    export HOPRD_API_HOST=$(printf $HOST_FORMAT $deployment 1 $env)
    if [ $env == "prod" ]; then
        export HOPRD_API_TOKEN=$PROD_TOKEN
    elif [ $env == "staging" ]; then
        export HOPRD_API_TOKEN=$STAGING_TOKEN
    fi
fi


# Create log folder
mkdir -p $log_folder
time=$(date '+%Y%m%d_%H%M%S')

echo "Starting CT in $env mode, storing logs in $log_folder"
uv run -m core --configfile ./.configs/core_${env}_config.yaml 2>&1 | tee "$log_folder/core_$time.log"