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

For the legacy economic model, the supported behavior is fixed by the app and configured only
through:

- `economic_model.legacy.proportion`
- `economic_model.legacy.apr`
- `economic_model.legacy.coefficients.a`
- `economic_model.legacy.coefficients.b`
- `economic_model.legacy.coefficients.lowerbound`
- `economic_model.legacy.coefficients.upperbound`

There is no free-form formula language in the config anymore.

Relevant channel controls under `channel`:

- `min_balance`
- `funding_amount`
- `funding_cooldown`
- `max_age`


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
