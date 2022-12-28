#!/bin/sh

export HOPR_NODE_1='some.node.there'
export HOPR_NODE_1_HTTP_URL="https://${HOPR_NODE_1}:3001"
export HOPR_NODE_1_WS_URL="ws://${HOPR_NODE_1}:3000"
export HOPR_NODE_1_API_KEY='xxx'

python ct.py
