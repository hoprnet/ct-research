#!/bin/bash

export $(grep -v '^#' .env | xargs)

# Default values
env="local"
count=5
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
    echo "http://0.0.0.0:$port"
}


# Parse command-line flags (long flags and short flags)
for arg in "$@"; do
    case $arg in
        --env=*)
            env="${arg#*=}"
            shift
            ;;
        --count=*)
            count="${arg#*=}"
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
        -c*)
            count="${arg#*=}"
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
            echo "Usage: $0 [--env=ENV] [--count=COUNT] [--deployment=DEPLOYMENT] [--log-folder=LOG_FOLDER]"
            exit 1
            ;;
    esac
done

if [ $env == "local" ]; then
    for i in $(seq 1 6); do
        export NODE_ADDRESS_${i}=$(get_local_node_address $i)
        export NODE_KEY_${i}="e2e-API-token^^"
    done

else
    # Check deployment if it's set to auto
    if [ $deployment == "auto" ]; then
        deployment=$(check_deployment $HOST_FORMAT $env)
    fi

    # Node parameters
    for i in $(seq 1 $count); do
        export NODE_ADDRESS_${i}=$(printf $HOST_FORMAT $deployment $i $env)
        export NODE_KEY_${i}=$TOKEN
    done
fi


# Create log folder
mkdir -p $log_folder
time=$(date '+%Y%m%d_%H%M%S')

echo "Starting core in $env mode ($count nodes), storing logs in $log_folder"
uv run -m core --configfile ./.configs/core_${env}_config.yaml 2>&1 | tee "$log_folder/core_$time.log"