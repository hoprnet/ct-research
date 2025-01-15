#!/bin/bash
export $(grep -v '^#' .env | xargs)

env=${1:-staging}
count=${2:-1}
deployment=${3:-auto}


healthyz() { echo $(curl -s -o /dev/null -w "%{http_code}" "$1/healthyz"); }

check_deployment() {
    if [ $(healthyz $(printf $1 "blue" "1" $2)) -eq 200 ]; then
        echo "blue"
        exit 1
    elif [ $(healthyz $(printf $1 "green" "1" $2)) -eq 200 ]; then
        echo "green"
        exit 1
    fi
}

if [ $deployment == "auto" ]; then
    deployment=$(check_deployment $HOST_FORMAT $env)
fi

# Node parameters
for i in $(seq 1 $count); do
    export NODE_ADDRESS_${i}=$(printf $HOST_FORMAT $deployment $i $env)
    export NODE_KEY_${i}=$TOKEN
done

echo "Starting core in $env mode"
python -m core --configfile ./.configs/core_${env}_config.yaml 2>&1 | tee logs_core.log