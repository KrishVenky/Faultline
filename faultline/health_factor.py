"""The one path everything computes health factor through -- the hand-walk
regression test and the Phase 2 solver's fixed-point loop both call this,
not their own reimplementation. Getting this wrong doesn't fail loudly; it
compounds silently across solver iterations into a plausible-looking wrong
cascade (BUILDLOG.md, 2026-09-05, "eMode was never accounted for")."""


def _threshold_fraction(record: dict) -> float:
    if record.get("liquidation_threshold_bps") is not None:
        return record["liquidation_threshold_bps"] / 10000
    if record.get("liquidate_collateral_factor") is not None:
        return float(record["liquidate_collateral_factor"])
    raise ValueError(f"record has no liquidation threshold: {record}")


def compute_health_factor(records: list[dict], prices_usd: dict[str, float]) -> dict:
    """`records`: one wallet's flat position records (aave.py/compound.py
    shape -- eMode-aware threshold already baked into each record by the
    fetch layer, this function doesn't know or care whether eMode applied).
    `prices_usd`: {asset_address.lower(): usd_price}. Only supply records
    with usage_as_collateral=True count toward collateral value; all borrow
    records count toward debt, regardless of protocol."""
    collateral_value_usd = 0.0
    debt_value_usd = 0.0

    for r in records:
        is_collateral = r["side"] == "supply" and r.get("usage_as_collateral")
        is_debt = r["side"] == "borrow"
        if not (is_collateral or is_debt):
            continue  # non-collateral supply (dust, or not opted in) doesn't affect HF -- no price needed

        price = prices_usd[r["asset_address"].lower()]
        amount = r["amount_wei"] / 10 ** r["asset_decimals"]
        value_usd = amount * price

        if is_collateral:
            collateral_value_usd += value_usd * _threshold_fraction(r)
        else:
            debt_value_usd += value_usd

    health_factor = (
        float("inf") if debt_value_usd == 0 else collateral_value_usd / debt_value_usd
    )
    return {
        "collateral_value_usd": collateral_value_usd,
        "debt_value_usd": debt_value_usd,
        "health_factor": health_factor,
    }
