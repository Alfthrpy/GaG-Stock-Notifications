from fisch_tracker.main import pages_for_tick, should_run_cleanup


def test_most_ticks_are_shallow_page_one_only():
    assert pages_for_tick(1, deep_sweep_every=5, shallow_pages=1, deep_pages=10) == 1
    assert pages_for_tick(2, deep_sweep_every=5, shallow_pages=1, deep_pages=10) == 1
    assert pages_for_tick(4, deep_sweep_every=5, shallow_pages=1, deep_pages=10) == 1


def test_every_nth_tick_is_a_deep_sweep():
    assert pages_for_tick(5, deep_sweep_every=5, shallow_pages=1, deep_pages=10) == 10
    assert pages_for_tick(10, deep_sweep_every=5, shallow_pages=1, deep_pages=10) == 10


def test_first_tick_is_always_deep_to_seed_the_epoch_sweep():
    # tick 0 = the very first sweep the process ever runs; going deep here
    # maximizes how many servers get a real (non-epoch) reference point ASAP.
    assert pages_for_tick(0, deep_sweep_every=5, shallow_pages=1, deep_pages=10) == 10


def test_should_run_cleanup_only_on_every_nth_tick():
    assert should_run_cleanup(0, every=200) is True
    assert should_run_cleanup(1, every=200) is False
    assert should_run_cleanup(199, every=200) is False
    assert should_run_cleanup(200, every=200) is True
    assert should_run_cleanup(400, every=200) is True
