"""Aave v3 close factor and collateral seizure math, sourced directly from
aave/aave-v3-core/contracts/protocol/libraries/logic/LiquidationLogic.sol
(BUILDLOG.md, 2026-09-05, "Two assumptions stated before the solver loop
is built"). Not from memory -- same standing rule as subgraph IDs and
Comet's index formula."""

CLOSE_FACTOR_HF_THRESHOLD = 0.95
DEFAULT_CLOSE_FACTOR = 0.50
MAX_CLOSE_FACTOR = 1.00


def close_factor(health_factor: float) -> float:
    return DEFAULT_CLOSE_FACTOR if health_factor > CLOSE_FACTOR_HF_THRESHOLD else MAX_CLOSE_FACTOR


def compute_seizure(
    total_debt_amount: float,
    debt_asset_price: float,
    collateral_asset_price: float,
    liquidation_bonus_bps: int,
    liquidation_protocol_fee_bps: int,
    user_collateral_balance: float,
    health_factor: float,
) -> dict:
    """One liquidation event against one (debt asset, collateral asset)
    pair. Assumes a rational liquidator covers the maximum the protocol
    allows (`maxLiquidatableDebt`), not less -- maximizes their bonus
    capture, same assumption as arbitrage closing a mispriced pool.
    Returns the amount actually removed from the wallet's collateral
    balance, and the (smaller) amount a liquidator receives and would
    sell into the market after the protocol's cut."""
    cf = close_factor(health_factor)
    debt_to_cover = total_debt_amount * cf

    bonus = liquidation_bonus_bps / 10_000
    base_collateral = debt_to_cover * debt_asset_price / collateral_asset_price
    max_collateral_to_liquidate = base_collateral * bonus

    if max_collateral_to_liquidate > user_collateral_balance:
        collateral_amount = user_collateral_balance
        debt_amount_needed = (collateral_amount * collateral_asset_price / debt_asset_price) / bonus
    else:
        collateral_amount = max_collateral_to_liquidate
        debt_amount_needed = debt_to_cover

    protocol_fee_rate = liquidation_protocol_fee_bps / 10_000
    if protocol_fee_rate:
        bonus_collateral = collateral_amount - collateral_amount / bonus
        protocol_fee = bonus_collateral * protocol_fee_rate
    else:
        protocol_fee = 0.0

    return {
        "close_factor": cf,
        "debt_repaid": debt_amount_needed,
        "collateral_seized_from_wallet": collateral_amount,
        "protocol_fee": protocol_fee,
        "liquidator_receives": collateral_amount - protocol_fee,
    }
