from faultline.config import UNISWAP_V3_ETHEREUM_SUBGRAPH_ID
from faultline.graphql_client import query_subgraph

# Pool selection rule (BUILDLOG.md, "Pool selection rule for price impact",
# 2026-09-05): a pool is eligible as a price-impact source for an asset only
# if the OTHER token is also in Faultline's own known asset universe
# (addresses already pulled from Aave/Compound reserve listings) -- never by
# raw TVL sort alone. A raw sort surfaces spam/fake-token pools: the
# ease.org/ez-cvxsteCRV pool reported ~$1.1 trillion fake TVL and would have
# won a naive sort (see BUILDLOG.md, live-verification entry). Highest
# totalValueLockedUSD wins only among pools that pass the address filter.

POOLS_BY_TOKEN_QUERY = """
query($token: Bytes!) {
  asToken0: pools(where: {token0: $token}, orderBy: totalValueLockedUSD, orderDirection: desc, first: 20) {
    id token0 { id symbol } token1 { id symbol } liquidity tick sqrtPrice totalValueLockedUSD feeTier
  }
  asToken1: pools(where: {token1: $token}, orderBy: totalValueLockedUSD, orderDirection: desc, first: 20) {
    id token0 { id symbol } token1 { id symbol } liquidity tick sqrtPrice totalValueLockedUSD feeTier
  }
}
"""


POOL_STATE_QUERY = """
query($pool: String!) {
  pool(id: $pool) {
    token0 { id decimals }
    token1 { id decimals }
    liquidity
    sqrtPrice
    tick
    token1Price
  }
}
"""


def fetch_pool_state(pool_address: str) -> dict:
    """Live current state of one pool -- for the live solver endpoint,
    not the frozen fixture (which uses a snapshot logged in BUILDLOG.md)."""
    data = query_subgraph(UNISWAP_V3_ETHEREUM_SUBGRAPH_ID, POOL_STATE_QUERY, {"pool": pool_address.lower()})
    pool = data["pool"]
    return {
        "token0_address": pool["token0"]["id"],
        "token0_decimals": int(pool["token0"]["decimals"]),
        "token1_address": pool["token1"]["id"],
        "token1_decimals": int(pool["token1"]["decimals"]),
        "liquidity_raw": int(pool["liquidity"]),
        "sqrt_price_x96": int(pool["sqrtPrice"]),
        "tick": int(pool["tick"]),
        "price_token1_per_token0": float(pool["token1Price"]),
    }


def eligible_pools_for_asset(asset_address: str, known_asset_addresses: set[str]) -> list[dict]:
    """Pools pairing `asset_address` against another address already in our
    own asset universe, sorted by TVL descending. Flat records."""
    asset_address = asset_address.lower()
    known = {a.lower() for a in known_asset_addresses}

    data = query_subgraph(
        UNISWAP_V3_ETHEREUM_SUBGRAPH_ID, POOLS_BY_TOKEN_QUERY, {"token": asset_address}
    )
    candidates = data["asToken0"] + data["asToken1"]

    eligible = []
    seen_pool_ids = set()
    for pool in candidates:
        if pool["id"] in seen_pool_ids:
            continue
        other = (
            pool["token1"] if pool["token0"]["id"].lower() == asset_address else pool["token0"]
        )
        if other["id"].lower() not in known:
            continue
        seen_pool_ids.add(pool["id"])
        eligible.append(
            {
                "pool_address": pool["id"],
                "asset_address": asset_address,
                "other_token_address": other["id"],
                "other_token_symbol": other["symbol"],
                "liquidity": int(pool["liquidity"]),
                "tick": int(pool["tick"]) if pool["tick"] is not None else None,
                "sqrt_price": int(pool["sqrtPrice"]),
                "total_value_locked_usd": float(pool["totalValueLockedUSD"]),
                "fee_tier": int(pool["feeTier"]),
            }
        )

    eligible.sort(key=lambda p: p["total_value_locked_usd"], reverse=True)
    return eligible


TICKS_QUERY = """
query($pool: String!, $skip: Int!) {
  ticks(
    where: {pool: $pool, liquidityGross_gt: 0}
    orderBy: tickIdx
    orderDirection: asc
    first: 1000
    skip: $skip
  ) {
    tickIdx
    liquidityNet
    liquidityGross
  }
}
"""

# The Graph caps `skip` at 5000 per field. Fine for Phase 1 (proving the
# fetch works on real data); if a Phase 2 pool has more initialized ticks
# than this covers, switch to tickIdx_gt cursoring instead of skip. Not
# built yet because the actual price-impact function (which determines how
# wide a tick window is even needed) doesn't exist until Phase 2.
_MAX_SKIP = 5000


def fetch_pool_ticks(pool_address: str) -> list[dict]:
    """All initialized ticks for a pool, paginated. Flat records."""
    pool_address = pool_address.lower()
    ticks = []
    skip = 0
    while skip <= _MAX_SKIP:
        data = query_subgraph(
            UNISWAP_V3_ETHEREUM_SUBGRAPH_ID, TICKS_QUERY, {"pool": pool_address, "skip": skip}
        )
        page = data["ticks"]
        ticks.extend(
            {
                "pool_address": pool_address,
                "tick_idx": int(t["tickIdx"]),
                "liquidity_net": int(t["liquidityNet"]),
                "liquidity_gross": int(t["liquidityGross"]),
            }
            for t in page
        )
        if len(page) < 1000:
            break
        skip += 1000
    return ticks


# Tick-walk swap simulation. Moved from the one-off scripts/hand_walk_cascade.py
# (BUILDLOG.md, 2026-09-05, "Cascade test: floor shock through the real
# pool") into the package, unchanged apart from being made reusable -- same
# two bugs already caught and fixed there, not reintroduced here:
#   1. `liquidity` (pool) and `liquidityNet` (each tick) are raw wei-scale
#      integers; a human-scale trade amount used against them directly
#      makes the pool look ~1e9x deeper than real. Caller must convert
#      both by dividing by 10**((decimals0+decimals1)/2) before calling.
#   2. `depth_exhausted` is only meaningful as an explicit stop_reason
#      ("ticks_exhausted"), not as "amount remaining > 0" -- that
#      comparison is always true when amount0_budget is infinite.

Q96 = 2**96


def walk_token0_sell(sqrt_p_start: float, liquidity_start: float, ticks_below: list[dict],
                      amount0_budget: float, target_sqrt_p: float | None = None) -> dict:
    """zeroForOne walk: sell token0 (the asset being shocked/liquidated)
    down through the real tick structure. `ticks_below` sorted descending
    by tick_idx, only ticks below the current price, with liquidity_net
    already converted to human scale. Stops at whichever comes first --
    `amount0_budget` exhausted, `target_sqrt_p` reached, or real
    initialized-tick liquidity runs out."""
    sqrt_p = sqrt_p_start
    L = liquidity_start
    amount0_remaining = amount0_budget
    amount0_used = 0.0
    total_amount1_out = 0.0
    ticks_crossed = 0

    for t in ticks_below:
        tick_sqrt_p = 1.0001 ** (t["tick_idx"] / 2)
        if target_sqrt_p is not None and tick_sqrt_p <= target_sqrt_p:
            sqrt_p_new = target_sqrt_p
            amount0_needed = L * (1 / sqrt_p_new - 1 / sqrt_p)
            if amount0_needed <= amount0_remaining:
                total_amount1_out += L * (sqrt_p - sqrt_p_new)
                amount0_used += amount0_needed
                amount0_remaining -= amount0_needed
                sqrt_p = sqrt_p_new
                return _swap_result(sqrt_p, L, amount0_used, amount0_remaining,
                                     total_amount1_out, ticks_crossed, "target_reached")

        amount0_to_boundary = L * (1 / tick_sqrt_p - 1 / sqrt_p)

        if amount0_to_boundary >= amount0_remaining:
            sqrt_p_new = 1 / (1 / sqrt_p + amount0_remaining / L)
            total_amount1_out += L * (sqrt_p - sqrt_p_new)
            amount0_used += amount0_remaining
            amount0_remaining = 0
            sqrt_p = sqrt_p_new
            return _swap_result(sqrt_p, L, amount0_used, amount0_remaining,
                                 total_amount1_out, ticks_crossed, "budget_filled")

        total_amount1_out += L * (sqrt_p - tick_sqrt_p)
        amount0_used += amount0_to_boundary
        amount0_remaining -= amount0_to_boundary
        sqrt_p = tick_sqrt_p
        L = L - t["liquidity_net"]
        ticks_crossed += 1

    return _swap_result(sqrt_p, L, amount0_used, amount0_remaining,
                         total_amount1_out, ticks_crossed, "ticks_exhausted")


def _swap_result(sqrt_p, L, amount0_used, amount0_remaining, amount1_out, ticks_crossed, stop_reason):
    return {
        "stop_reason": stop_reason,
        "depth_exhausted": stop_reason == "ticks_exhausted",
        "amount0_used": amount0_used,
        "amount0_unfilled": amount0_remaining if amount0_remaining != float("inf") else None,
        "amount1_out": amount1_out,
        "ticks_crossed": ticks_crossed,
        "final_price_token1_per_token0": sqrt_p ** 2,
        "final_sqrt_p": sqrt_p,
        "final_liquidity": L,
    }


def human_scale_liquidity(liquidity_raw: int, decimals0: int, decimals1: int) -> float:
    return liquidity_raw / (10 ** ((decimals0 + decimals1) / 2))


def compute_depth_profile(liquidity_start: float, ticks_crossed: list[dict]) -> dict:
    """How fast real liquidity collapses moving away from the current
    price -- the concentrated-liquidity finding (BUILDLOG.md, 2026-09-06,
    "Reference cascade locked: two findings, layered"). Computed directly
    from the same tick data a reposition/walk crosses, not estimated.
    Shared by the frozen fixture generator and the live endpoint so both
    report this the same way. `curve` is the full per-tick trace (small --
    at most however many ticks the reposition crossed, typically under
    100) for the depth-chart inset (section 9 step 3): real data points,
    not a sampled/smoothed approximation."""
    L = liquidity_start
    ticks_to_pct: dict[float, int] = {}
    thresholds = [50, 10, 5, 1, 0.1]
    curve = [{"ticks_crossed": 0, "tick_idx": ticks_crossed[0]["tick_idx"] + 1 if ticks_crossed else None, "liquidity": L}]
    for i, t in enumerate(ticks_crossed, start=1):
        L -= t["liquidity_net"]
        curve.append({"ticks_crossed": i, "tick_idx": t["tick_idx"], "liquidity": L})
        pct_of_start = L / liquidity_start * 100
        for threshold in thresholds:
            if threshold not in ticks_to_pct and pct_of_start <= threshold:
                ticks_to_pct[threshold] = i
    return {
        "starting_liquidity": liquidity_start,
        "ticks_to_depletion_pct": ticks_to_pct,
        "curve": curve,
    }
