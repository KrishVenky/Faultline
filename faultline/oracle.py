"""Live AaveOracle contract reads. NOT the Aave subgraph's PriceOracleAsset
mirror -- BUILDLOG.md, 2026-09-05, "Aave subgraph's oracle price mirror is
stale": that mirror was found wrong by months for every asset checked
(wstETH never populated at all). This is the actual source Aave's Pool
contract reads at liquidation time.

Contract address verified from bgd-labs/aave-address-book
(src/AaveV3Ethereum.sol), not a search result -- same standing rule as
subgraph IDs (CLAUDE.md section 10).
"""

import httpx

AAVE_ORACLE_ADDRESS = "0x54586bE62E3c3580375aE3723C145253060Ca0C2"
ETH_RPC_URL = "https://ethereum-rpc.publicnode.com"
GET_ASSET_PRICE_SELECTOR = "b3596f07"  # keccak256("getAssetPrice(address)")[:4]


def fetch_oracle_price_usd(asset_address: str) -> float:
    """AaveOracle.getAssetPrice(asset) -> USD price, 8 decimals."""
    addr_padded = asset_address.lower().removeprefix("0x").zfill(64)
    data = f"0x{GET_ASSET_PRICE_SELECTOR}{addr_padded}"
    response = httpx.post(
        ETH_RPC_URL,
        json={
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{"to": AAVE_ORACLE_ADDRESS, "data": data}, "latest"],
            "id": 1,
        },
        timeout=15.0,
    )
    response.raise_for_status()
    body = response.json()
    if "error" in body:
        raise RuntimeError(f"eth_call failed for {asset_address}: {body['error']}")
    return int(body["result"], 16) / 1e8


def fetch_chain_head() -> int:
    response = httpx.post(
        ETH_RPC_URL,
        json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
        timeout=15.0,
    )
    response.raise_for_status()
    return int(response.json()["result"], 16)
