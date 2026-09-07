import os

from dotenv import load_dotenv

load_dotenv()

GRAPH_API_KEY = os.environ["GRAPH_API_KEY"]

GRAPH_GATEWAY_URL = "https://gateway.thegraph.com/api/subgraphs/id/{subgraph_id}"

# Every ID below was pulled from the protocol's own docs/README and verified
# live (block number checked against chain head) on 2026-09-05. See
# BUILDLOG.md "Live verification" entry for the full trail, including three
# search-result-derived IDs that turned out wrong before these were found.
# Do not replace one of these from a search result without re-verifying live
# first (CLAUDE.md working style rule).

AAVE_V3_ETHEREUM_SUBGRAPH_ID = "Cd2gEDVeqnjBn1hSeqFMitw8Q1iiyV9FYUZkLNRcL87g"
COMPOUND_V3_ETHEREUM_SUBGRAPH_ID = "5nwMCSHaTqG3Kd2gHznbTXEnZ9QNWsssQfbHhDqQSQFp"
UNISWAP_V3_ETHEREUM_SUBGRAPH_ID = "5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV"

RAY = 10**27  # Aave index precision (1e27)
BASE_INDEX_SCALE = 10**15  # Comet index precision, from CometCore.sol (compound-finance/comet)
