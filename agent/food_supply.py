"""Wheat-cookie supply arithmetic. Unknown stocks never authorize sowing."""
from math import ceil


def plan_current_gap(satiety, capacity, cookie_stock, wheat_stock=None,
                     queued_seeds=None, growing_wheat=None, seed_stock=None):
    for value in (satiety, capacity, cookie_stock):
        if type(value) is not int or value < 0:
            raise ValueError('餐桌和饼干数量必须是非负整数')
    if capacity <= 0 or satiety > capacity:
        raise ValueError('餐桌容量异常')
    deficit = capacity - satiety
    cookies_needed = ceil(deficit / 25)
    to_make = max(0, cookies_needed - cookie_stock)
    if not to_make:
        return dict(ready=True, satiety_deficit=deficit, cookies_needed=cookies_needed,
                    cookies_to_make=0, wheat_required=0, seeds_required=0, seeds_to_add=0, unknown=[])
    result = plan_supply(cookies_needed, cookie_stock=cookie_stock, wheat_stock=wheat_stock,
                         queued_seeds=queued_seeds, growing_wheat=growing_wheat, seed_stock=seed_stock)
    result.update(satiety_deficit=deficit, cookies_needed=cookies_needed,
                  cookies_to_make=to_make, wheat_required=to_make * 4)
    return result


def plan_supply(daily_cookies, *, cookie_stock, wheat_stock, queued_seeds,
                growing_wheat, seed_stock, days=1):
    """queued_seeds are one future harvest each; do not assume free seed recycling.

    CBT3 recipe: 4 ordinary wheat/cookie. Ordinary wheat seed: 4 wheat/harvest.
    growing_wheat is already the expected output, not the number of occupied plots.
    """
    stocks = dict(cookie_stock=cookie_stock, wheat_stock=wheat_stock,
                  queued_seeds=queued_seeds, growing_wheat=growing_wheat, seed_stock=seed_stock)
    unknown = [key for key, value in stocks.items() if value is None]
    if daily_cookies is None:
        unknown.insert(0, 'daily_cookies')
    for value in [daily_cookies, days, *stocks.values()]:
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError('备粮数量必须是非负整数或未知')
    if days < 1:
        raise ValueError('备粮天数至少为1')
    if unknown:
        return dict(ready=False, unknown=unknown, seeds_to_add=None)
    target = daily_cookies * days
    cookies_to_make = max(0, target - cookie_stock)
    wheat_required = cookies_to_make * 4
    wheat_deficit_now = max(0, wheat_required - wheat_stock)
    wheat_deficit_after_harvest = max(0, wheat_deficit_now - growing_wheat - queued_seeds * 4)
    seeds_required = ceil(wheat_deficit_after_harvest / 4)
    return dict(ready=True, unknown=[], daily_cookies=daily_cookies, days=days,
                target_cookies=target, cookies_to_make=cookies_to_make,
                wheat_required=wheat_required, wheat_deficit_now=wheat_deficit_now,
                expected_wheat=growing_wheat + queued_seeds * 4,
                seeds_required=seeds_required, seeds_to_add=min(seed_stock, seeds_required),
                seed_shortage=max(0, seeds_required - seed_stock))


def estimate_daily_cookies(previous, current, minimum_hours=6):
    """Use feeding snapshots only; empty tables and external changes invalidate a rate.

    Each snapshot contains time (epoch seconds), before, after and capacity.
    Assumes no external feeding/removal between snapshots; caller must disclose this.
    """
    if not previous:
        return None
    elapsed = (current['time'] - previous['time']) / 3600
    if elapsed < minimum_hours or elapsed > 72:
        return None
    if previous['capacity'] != current['capacity'] or current['before'] <= 0:
        return None
    consumed = previous['after'] - current['before']
    if consumed <= 0:
        return None
    return ceil(consumed / elapsed * 24 / 25)
