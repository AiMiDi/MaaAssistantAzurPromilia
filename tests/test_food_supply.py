from food_supply import plan_supply, estimate_daily_cookies, plan_current_gap


def test_deducts_cookies_wheat_and_pending_harvest():
    p = plan_supply(72, cookie_stock=12, wheat_stock=100, queued_seeds=10,
                    growing_wheat=20, seed_stock=50)
    assert p['cookies_to_make'] == 60
    assert p['wheat_required'] == 240
    assert p['wheat_deficit_now'] == 140
    assert p['seeds_required'] == 20
    assert p['seeds_to_add'] == 20


def test_existing_cookie_stock_avoids_unnecessary_sowing():
    p = plan_supply(72, cookie_stock=717, wheat_stock=0, queued_seeds=0,
                    growing_wheat=0, seed_stock=10)
    assert p['seeds_to_add'] == 0


def test_unknown_growing_stock_does_not_become_zero():
    p = plan_supply(72, cookie_stock=0, wheat_stock=0, queued_seeds=0,
                    growing_wheat=None, seed_stock=100)
    assert not p['ready'] and p['seeds_to_add'] is None


def test_seeds_round_up_and_report_shortage():
    p = plan_supply(3, cookie_stock=0, wheat_stock=1, queued_seeds=0,
                    growing_wheat=0, seed_stock=2)
    assert p['seeds_required'] == 3 and p['seed_shortage'] == 1


def test_daily_estimate_uses_elapsed_time_not_table_capacity():
    previous = dict(time=0, after=1800, capacity=1800)
    current = dict(time=12*3600, before=900, capacity=1800)
    assert estimate_daily_cookies(previous, current) == 72
    current['before'] = 0
    assert estimate_daily_cookies(previous, current) is None
    current.update(before=900, time=60)
    assert estimate_daily_cookies(previous, current) is None


def test_current_gap_and_existing_stock():
    plan = plan_current_gap(525,1800,0, wheat_stock=100, queued_seeds=10,
                            growing_wheat=20, seed_stock=100)
    assert plan['cookies_needed'] == 51
    assert plan['wheat_required'] == 204
    assert plan['seeds_required'] == 11
    assert plan_current_gap(525,1800,717)['seeds_to_add'] == 0
    assert plan_current_gap(1800,1800,0)['cookies_to_make'] == 0
