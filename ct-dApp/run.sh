#!/bin/sh
export HOPR_NODE='127.0.0.1'
export HOPR_NODE_HTTP_URL="http://${HOPR_NODE}:PORT_FIELD"
export HOPR_NODE_WS_URL="ws://${HOPR_NODE}:PORT_FIELD"
export HOPR_NODE_API_KEY='%th1s-IS-a-S3CR3T-ap1-PUSHING-b1ts-TO-you%'
export AGG_HTTP_POST_URL='http://localhost:8080/aggregator/list'

while getopts e:p: flag
do
    case "${flag}" in
        e) element=${OPTARG};;
        p) port=${OPTARG};; # 13304
    esac
done

clear
if [ "$element" = "ct" ]; then
    echo "Running ct"
    python -m ct --plotf plots --latcount 100
elif [ "$element" = "nw" ]; then
    echo "Running NetWatcher"
    python -m netwatcher --port $port
elif [ "$element" = "agg" ]; then
    echo "Running Aggregator"
    python -m aggregator
else
    echo "Invalid element: $element"
fi

