#!/bin/sh

export HOPR_NODE_1='127.0.0.1'
export HOPR_NODE_1_HTTP_URL="http://${HOPR_NODE_1}:13305"
export HOPR_NODE_1_WS_URL="ws://${HOPR_NODE_1}:13305"
export HOPR_NODE_1_API_KEY='%th1s-IS-a-S3CR3T-ap1-PUSHING-b1ts-TO-you%'
export RPCH_NODES_API_ENDPOINT='some_api_endpoint_test'

python -m economic_handler