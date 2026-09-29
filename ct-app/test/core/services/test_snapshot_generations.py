from core.services.snapshot_generations import SnapshotGenerations


def test_pop_stale_returns_keys_not_seen_since_last_start():
    generations = SnapshotGenerations[str]()
    generations.start()
    generations.touch("kept")
    generations.touch("gone")
    generations.touch("forgotten")
    generations.forget("forgotten")

    generations.start()
    generations.touch("kept")

    assert generations.pop_stale() == ["gone"]
    assert generations.pop_stale() == []


def test_nothing_is_stale_without_a_new_generation():
    generations = SnapshotGenerations[str]()
    generations.touch("a")

    assert generations.pop_stale() == []
