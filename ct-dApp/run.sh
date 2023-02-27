#!/bin/sh

export HOPR_NODE_1='192.168.1.134'
export HOPR_NODE_1_HTTP_URL="http://${HOPR_NODE_1}:3001"
export HOPR_NODE_1_WS_URL="ws://${HOPR_NODE_1}:3000"
export HOPR_NODE_1_API_KEY='!5qxc9Lp1BE7IFQ-nrtttU'

python3 ct.py
