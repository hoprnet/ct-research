# Aggregator

The Aggregator acts as a REST server which creates routes to receive NetWatchers available-peer-lists and expose metrics for monitoring. It solves NW-Peer conflicts based on a custom algorithm. It is connected to a DB on GCP to store metrics received from the NWs.

Only one instance needs to run at the same time. A backup instance takes over of necessary.