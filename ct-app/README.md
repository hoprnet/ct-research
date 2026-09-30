# ct-app

`ct-app` distributes wxHOPR through 1-hop messages in the Dufour network. In practice it
replaces the staking rewards users used to earn in the current staking season.

## Runtime

Install dependencies:

```bash
uv sync --frozen
```

Run the app with:

```sh
uv run python -m core --configfile ./.configs/core_staging_config.yaml
```

### Environment

Parameter | Required | Notes
--|--|--
`HOPRD_API_HOST` | no | Defaults to `http://127.0.0.1:3001`
`HOPRD_API_TOKEN` | yes | Required startup secret
`BLOKLI_URL` | yes unless `blokli.url` is set in the config | Intended primary provider endpoint; use the GraphQL base URL (for example `http://localhost:8080` or `http://localhost:8080/graphql`)
`BLOKLI_TOKEN` | yes unless `blokli.token` is set in the config | Intended primary provider secret
`LOG_LEVEL` | no | Global or per-library log level overrides

`LOG_LEVEL` examples:

- `LOG_LEVEL=debug`
- `LOG_LEVEL=info,core.api=debug,mixins=warning`

### Config

The repo-owned config files live under `.configs/`. The parser shape is also reflected in
`test/test_config.yaml`.

### Incentive model

CT uses a burst model. Each CT node runs rounds
on its own. At the start of a round it shuffles the relayers it considers eligible. It then starts
a burst to each of them every `step = ct_node_count × target_relayer_interval / N` seconds, without
waiting for earlier bursts to finish.

A relayer is eligible when this CT node can reach it and it has at least `min_outgoing_channels`
open outgoing channels, each holding at least `min_channel_balance`. It must also not be a CT node
or in `peer.excluded_peers`. Stake, safe balance and location play no part.

A burst lasts `burst_duration` and goes over a 1-hop session through the relayer.
`burst_rate` is the traffic the relayer forwards and gets paid for. Every packet crosses the
relayer twice, out to the destination and back as its echo, and it earns a ticket each time. So a
CT node sends at `burst_rate / 2`, and each echoed packet costs two tickets. The packet rate counts
the full session MTU, because every packet carries a SURB. Each packet carries MTU minus SURB bytes
of generated data. Relayers are paid only through the tickets on the packets they relay. Nothing
else is computed or paid.

The `incentive` config section holds the parameters:

- `incentive.min_outgoing_channels`
- `incentive.min_channel_balance`
- `incentive.burst_rate` (Mbit/s)
- `incentive.burst_duration`
- `incentive.target_relayer_interval`
- `incentive.max_concurrent_bursts_per_ct` (`0` = no limit; above it, rounds get longer)
- `incentive.ct_node_count`

Every round logs its plan: size, step, concurrency, packets per burst, and the projected maximum
monthly cost at the current ticket price. It also logs the month-to-date sent and echoed packets
and their cost.

### Channels

CT does not open, fund or close channels. The hoprd node it talks to does, through its `ChannelLifecycle` strategy. CT only follows the channels through Blokli's `openedChannelGraphUpdated` subscription, to know which relays it can send through and which relayers have enough funded outgoing channels to be eligible.

Every CT node needs a channel to every relay it uses, because messages go `A -> relay -> B` and come back `B -> relay -> A`. A starting point for the CT nodes' hoprd config, which opens a channel to every connected peer, tops it up, and closes it only when the peer has been unseen for a while:

```yaml
strategy:
  strategies:
    - ChannelLifecycle:
        population:
          target_open_channels: 10000  # above the network size: open to every eligible peer
        eligibility:
          require_currently_connected: true
          min_peer_quality_score: 0.0
          demote_non_forwarding_peers: false
        funding:
          initial_capacity: "64 MiB"  # size to CT's traffic; the default 1 GiB locks ~3k wxHOPR per channel
          topup_capacity: "64 MiB"
          lower_capacity_threshold: "16 MiB"
        closure:
          close_below_quality_score: 0.0
          close_after_disconnected_ticks: 1000
          close_when_peer_unseen_for: "3d"
```


### Metrics

The metrics inventory is generated from the source code:

```bash
uv run python scripts/generate_metrics_doc.py
```

The generated output is checked by the local pre-commit hook in `.pre-commit-config.yaml` and
written to [METRICS.md](./METRICS.md).

## Development

Requirements:
- Python 3.14.6+
- `uv`

Setup:
```bash
uv sync --frozen
```

Common commands:
```bash
make test
make fmt
make run
```

## Contact

- [Twitter](https://twitter.com/hoprnet)
- [Telegram](https://t.me/hoprnet)
- [Medium](https://medium.com/hoprnet)
- [Reddit](https://www.reddit.com/r/HOPR/)
- [Email](mailto:contact@hoprnet.org)
- [Discord](https://discord.gg/5FWSfq7)
- [Youtube](https://www.youtube.com/channel/UC2DzUtC90LXdW7TfT3igasA)

## License

[GPL v3](LICENSE) © HOPR Association
