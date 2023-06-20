#!/bin/sh

export HOPR_NODE_1='127.0.0.1'
export HOPR_NODE_1_HTTP_URL="http://${HOPR_NODE_1}:13305"
export HOPR_NODE_1_WS_URL="ws://${HOPR_NODE_1}:13305"
export HOPR_NODE_1_API_KEY='%th1s-IS-a-S3CR3T-ap1-PUSHING-b1ts-TO-you%'

while getopts e:: flag
do
    case "${flag}" in
        e) element=${OPTARG};;
    esac
done

if [ "$element" = "ct" ]; then
    echo "Running ct"
    python -m ct --plotf plots --latcount 100
elif [ "$element" = "nw" ]; then
    echo "Running NetWatcher"
    python -m netwatcher
elif [ "$element" = "agg" ]; then
    echo "Running Aggregator"
    python -m aggregator
else
    echo "Invalid element: $element"
fi