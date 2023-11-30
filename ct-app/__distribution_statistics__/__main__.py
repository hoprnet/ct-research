import random

import matplotlib.pyplot as plt
from database import DatabaseConnection, Reward
from sqlalchemy import case
from sqlalchemy.sql import func, text


def get_all_peers() -> list[str]:
    with DatabaseConnection() as session:
        peers = session.query(Reward.peer_id).distinct().all()
    return [peer for (peer,) in peers]


def get_first_try_stats_by_batch_by_peer(peer: str = None) -> dict[int, int]:
    with DatabaseConnection() as session:
        if peer is not None:
            RankedRows = (
                session.query(
                    Reward.peer_id,
                    Reward.timestamp,
                    Reward.effective_count,
                    Reward.expected_count,
                    Reward.issued_count,
                    func.row_number()
                    .over(
                        partition_by=(Reward.peer_id, Reward.timestamp),
                        order_by=Reward.expected_count.desc(),
                    )
                    .label("row_num"),
                )
                .filter(Reward.peer_id == peer)
                .cte("RankedRows")
            )
        else:
            RankedRows = session.query(
                Reward.peer_id,
                Reward.timestamp,
                Reward.effective_count,
                Reward.expected_count,
                Reward.issued_count,
                func.row_number()
                .over(
                    partition_by=(Reward.peer_id, Reward.timestamp),
                    order_by=Reward.expected_count.desc(),
                )
                .label("row_num"),
            ).cte("RankedRows")

        BatchMarkers = session.query(
            RankedRows.c.peer_id,
            RankedRows.c.timestamp,
            RankedRows.c.expected_count,
            RankedRows.c.effective_count,
            RankedRows.c.issued_count,
            RankedRows.c.row_num,
            case(
                (
                    text(
                        "EXTRACT(EPOCH FROM (timestamp - LAG(timestamp, 1, timestamp) OVER (ORDER BY timestamp))) > 3600"
                    ),
                    1,
                ),
                else_=0,
            ).label("is_new_batch"),
        ).cte("BatchMarkers")

        BatchGroups = session.query(
            BatchMarkers.c.peer_id,
            BatchMarkers.c.timestamp,
            BatchMarkers.c.expected_count,
            BatchMarkers.c.effective_count,
            BatchMarkers.c.issued_count,
            BatchMarkers.c.row_num,
            func.sum(BatchMarkers.c.is_new_batch)
            .over(order_by=BatchMarkers.c.timestamp)
            .label("batch_group"),
        ).cte("BatchGroups")

        FilteredRows = (
            session.query(
                BatchGroups.c.peer_id,
                BatchGroups.c.timestamp,
                BatchGroups.c.expected_count,
                BatchGroups.c.effective_count,
                BatchGroups.c.issued_count,
                BatchGroups.c.row_num,
                BatchGroups.c.batch_group,
            )
            .filter(BatchGroups.c.row_num == 1)
            .cte("FilteredRows")
        )

        FirstTryCount = (
            session.query(
                FilteredRows.c.batch_group.label("batch_group"),
                func.min(FilteredRows.c.timestamp).label("start"),
                func.sum(FilteredRows.c.expected_count).label("expected"),
                func.sum(FilteredRows.c.issued_count).label("issued"),
                func.sum(FilteredRows.c.effective_count).label("relayed"),
            )
            .group_by(FilteredRows.c.batch_group)
            .cte("FirstTryCount")
        )

        final_query = session.query(
            FirstTryCount.c.batch_group,
            FirstTryCount.c.start,
            FirstTryCount.c.expected,
            FirstTryCount.c.issued,
            FirstTryCount.c.relayed,
        )

        entries = final_query.all()

    return {
        batch: (expected, issued, relayed)
        for batch, _, expected, issued, relayed in entries
    }


def main():
    fig, axes = plt.subplots(4, 4, sharex=True, sharey=True)
    axes = axes.flatten()

    chosen_peers = random.sample(get_all_peers(), len(axes))

    for peer, ax in zip(chosen_peers, axes):
        first_try_stats = get_first_try_stats_by_batch_by_peer(peer)

        expected = [expected for expected, _, _ in first_try_stats.values()]
        ax.plot(first_try_stats.keys(), expected, label="expected")

        relayed = [relayed for _, _, relayed in first_try_stats.values()]
        ax.plot(first_try_stats.keys(), relayed, label="relayed")

        # print text in graph
        peer_t = ax.text(
            0.05,
            0.9,
            peer,
            horizontalalignment="left",
            verticalalignment="center",
            transform=ax.transAxes,
            fontsize=6,
            color="white",
        )
        stat_t = ax.text(
            0.05,
            0.7,
            f"{sum(relayed)}/{sum(expected)}",
            horizontalalignment="left",
            verticalalignment="center",
            transform=ax.transAxes,
            fontsize=6,
            color="white",
        )

        peer_t.set_bbox(dict(facecolor="blue", alpha=0.5, linewidth=0))
        stat_t.set_bbox(dict(facecolor="blue", alpha=0.5, linewidth=0))

        ax.legend(fontsize=6)

    # set top, bottom, left and right spacing to 0
    fig.subplots_adjust(
        top=0.98, bottom=0.02, left=0.02, right=0.98, hspace=0.1, wspace=0.1
    )
    plt.show()


if __name__ == "__main__":
    main()
