#!/bin/sh

export HOPR_NODE_1='zero_elbe_white_deimos.playground.hoprnet.org'
export HOPR_NODE_1_HTTP_URL="https://${HOPR_NODE_1}:3001"
export HOPR_NODE_1_WS_URL="ws://${HOPR_NODE_1}:3000"
export HOPR_NODE_1_API_KEY='3#BA8d4b8e7d720D40e9daf2'

python ct.py
