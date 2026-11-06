# Blokli subscriptions resend a full snapshot on every (re)connection, but never mention entries
# that disappeared while disconnected. Entries not resent within this delay after a connection
# are considered gone.
SNAPSHOT_SWEEP_DELAY_SECONDS = 60.0
