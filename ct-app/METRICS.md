# METRICS

Generated from `core/` metric definitions by `scripts/generate_metrics_doc.py`.

| Metric | Type | Labels | Description | Source |
| --- | --- | --- | --- | --- |
| `ct_active_workers` | `Gauge` | `-` | Number of active message workers (0=stopped, 10=running) | `core/messages/message_metrics.py` |
| `ct_balance` | `Gauge` | `token` | Node balance | `core/mixins/state.py` |
| `ct_balance_multiplier` | `Gauge` | `-` | factor to multiply the balance by | `core/node.py` |
| `ct_batch_schedule_failures_total` | `Counter` | `-` | Total batch send scheduling failures in the message workers | `core/messages/message_metrics.py` |
| `ct_blokli_calls` | `Counter` | `type, target, result` | Total Blokli API calls | `core/blokli/blokli_provider.py` |
| `ct_channel_funds` | `Gauge` | `-` | Total funds in out. channels | `core/mixins/channel/actions.py` |
| `ct_channel_operation` | `Gauge` | `op, success` | Channel operation | `core/components/node_helper.py` |
| `ct_channels` | `Gauge` | `direction` | Node channels | `core/mixins/channel/actions.py` |
| `ct_eligible_peers` | `Gauge` | `-` | # of eligible peers for rewards | `core/mixins/economic_system.py` |
| `ct_message_count` | `Gauge` | `address, model` | messages one should receive / year | `core/mixins/economic_system.py` |
| `ct_message_e2e_latency_seconds` | `Histogram` | `-` | End-to-end message latency from queue entry to send completion | `core/messages/message_metrics.py` |
| `ct_message_latency_seconds` | `Histogram` | `phase` | Message processing latency | `core/messages/message_metrics.py` |
| `ct_message_requeue_total` | `Counter` | `reason` | Total messages requeued for retry | `core/messages/message_metrics.py` |
| `ct_message_sending_request` | `Gauge` | `relayer` |  | `core/api/session.py` |
| `ct_messages_delays` | `Histogram` | `relayer` | Messages delays | `core/api/session.py` |
| `ct_messages_processed_total` | `Counter` | `-` | Total messages processed | `core/messages/message_metrics.py` |
| `ct_messages_scheduled_total` | `Counter` | `-` | Total messages scheduled for sending (enqueued to AsyncLoop) | `core/messages/message_metrics.py` |
| `ct_messages_sent_failed_total` | `Counter` | `reason` | Total messages that failed to send | `core/messages/message_metrics.py` |
| `ct_messages_sent_success_total` | `Counter` | `-` | Total messages successfully sent (batch send completed) | `core/messages/message_metrics.py` |
| `ct_messages_stats` | `Gauge` | `type, relayer` |  | `core/api/session.py` |
| `ct_network_update_drains_total` | `Counter` | `-` | Network update drain executions | `core/services/network_update_coordinator.py` |
| `ct_network_update_pending` | `Gauge` | `-` | Whether a network update refresh is pending | `core/services/network_update_coordinator.py` |
| `ct_network_update_requests_total` | `Counter` | `source` | Network update refresh requests | `core/services/network_update_coordinator.py` |
| `ct_node_health` | `Gauge` | `-` | Node health | `core/mixins/state.py` |
| `ct_peer_channels_balance` | `Gauge` | `address` | Balance in outgoing channels | `core/types/peer.py` |
| `ct_peer_delay` | `Gauge` | `address` | Delay between two messages | `core/types/peer.py` |
| `ct_peer_safe_count` | `Gauge` | `address, safe` | Number of nodes linked to the safes | `core/types/peer.py` |
| `ct_peers_count` | `Gauge` | `-` | Node peers | `core/mixins/peers_discovery.py` |
| `ct_queue_size` | `Gauge` | `-` | Size of the message queue | `core/types/message_queue.py` |
| `ct_redeemed_rewards` | `Gauge` | `address` | Redeemed rewards | `core/mixins/network_sync.py` |
| `ct_send_plan_eligible_peers` | `Gauge` | `-` | Eligible peers in latest send plan | `core/services/send_plan_coordinator.py` |
| `ct_send_plan_steps_total` | `Counter` | `-` | Send plan steps emitted | `core/services/send_plan_coordinator.py` |
| `ct_session_count` | `Gauge` | `-` | Number of active sessions | `core/messages/message_metrics.py` |
| `ct_session_lifecycle_transitions_total` | `Counter` | `event` | Session lifecycle transitions | `core/services/session_lifecycle_coordinator.py` |
| `ct_session_open_events_total` | `Counter` | `result` | Session open lifecycle events recorded by the message workers | `core/messages/message_metrics.py` |
| `ct_session_operation` | `Gauge` | `relayer, op, success` | Session operation | `core/components/node_helper.py` |
| `ct_ticket_stats` | `Gauge` | `type` | Ticket stats | `core/mixins/state.py` |
| `ct_topology_size` | `Gauge` | `-` | Size of the topology | `core/mixins/channel/actions.py` |
| `ct_unique_peers` | `Gauge` | `type` | Unique peers | `core/mixins/peers_discovery.py` |
| `ct_worker_loop_events_total` | `Counter` | `event` | Worker loop events recorded by the message workers | `core/messages/message_metrics.py` |
| `ct_worker_messages_total` | `Counter` | `worker_id` | Messages processed per worker (Phase 2 parallel processing) | `core/messages/message_metrics.py` |
