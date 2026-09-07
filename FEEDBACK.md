# Uniswap Stack Feedback -- Faultline

Submitted for "Best Uniswap Stack Contribution," ETHOnline 2026. This is
feedback from actually building the price-impact half of a systemic-risk
solver on the v3 subgraph and QuoterV2, not a token import that gets called
once for a screenshot. Specific numbers, specific bugs, specific asks.

## What Uniswap v3 is actually load-bearing for here

Faultline's whole thesis is that a forced liquidation sale on one lending
protocol can crash a shared collateral asset's price against real pool
depth, liquidating an unrelated wallet on a different protocol. That
sentence is meaningless without tick-level liquidity data -- a flat
slippage assumption would have made every result invented. The v3
subgraph's `Tick.liquidityNet`/`liquidityGross` and `Pool.liquidity`/
`sqrtPrice` fields are exactly the primitives that make it possible to
simulate a real swap's price impact without running a node. We built our
own swap-invariant walk (`faultline/uniswap.py::walk_token0_sell`) directly
from these fields, tick by tick, same math as the pool contract itself.

## The subgraph ID problem, and how docs.uniswap.org actually solved it

First pass, we sourced a v3 mainnet subgraph ID from a web search result
labeled "Uniswap V3 Official." It resolved: `NOT INDEXED... Ethereum
endpoints have been deprecated and this Subgraph has not been migrated`,
curated by a personal account, last updated 4 years ago. We'd have shipped
a demo on dead data if we hadn't checked live before trusting it.

The fix was `developers.uniswap.org`'s own Subgraphs Overview page, which
states plainly: "Explorer links and endpoints in this page are examples of
public deployments. They are not official deployments and may not be
actively maintained by Uniswap Labs... Confirm the deployment is actively
indexed." That warning is exactly right and would have saved us the dead
end if we'd read it first instead of trusting a search result. Suggestion:
that warning deserves to be more prominent than a docs-page caveat --
maybe a live status indicator next to each listed ID, or the ID list
itself pulled from a source that can't silently go stale (a versioned
JSON in the same repo as the subgraph code, not a wiki-style docs page).
The correct ID we ended up using, confirmed from that same page:
`5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV`.

## The tick-inclusion bug QuoterV2 caught for us

We had a real bug: our swap walk excluded the pool's own current tick from
a downward (zeroForOne) walk. Most of the time this doesn't matter --
but when the current tick happens to be itself initialized (which it was,
carrying a liquidityNet of roughly -2.58M in human-scale units, a large
fraction of the pool's total liquidity at the time), excluding it drove
our own liquidity tracker negative. Negative liquidity is impossible in a
real pool, which is what told us something was wrong.

Before trusting our fix, we cross-checked our walk function against
`QuoterV2.quoteExactInputSingle` on the real deployed contract
(`0x61fFE014bA17989E743c5F6cB21bF9697530B21e`) for the identical trade.
Our numbers matched to 4 significant figures -- same tick crossed, output
within 0.01%. That gave us confidence to trust our own implementation
going forward, and separately, to trust a much bigger and stranger-looking
result later (a 2,000 wstETH sale into the same pool crashing price
99.9996% -- confirmed independently via QuoterV2 with zero code of ours
involved, before we believed it was real and not a bug).

**This is the actual ask**: `quoteExactInputSingle`'s calldata is a single
ABI-encoded struct tuple, and we had to derive the function selector
(`c6a5026a`) and hand-build the encoding ourselves since our stack is
Python, not ethers.js. A short "call QuoterV2 with raw eth_call, no SDK"
snippet in the docs -- selector, param order, a worked example -- would
have saved real time for anyone not building in a JS-first stack, and
QuoterV2 is genuinely valuable as a way to sanity-check custom AMM math
against ground truth, which is a use case beyond just "get a swap quote
for my frontend."

## A finding that surfaced only because tick data exists

Independent of anything we set out to prove: the wstETH/WETH 1bps pool we
used has essentially no depth outside a narrow band around its current
price. Liquidity there drops to under 5% of its starting value after just
4 ticks crossed, verified both through our own tick walk and through
QuoterV2 directly. That's a real, useful fact about how liquidity actually
distributes on a low-fee tier for a correlated pair, and we'd never have
found it without per-tick data being queryable at all. If there's a way to
surface "effective depth within N% of current price" as a first-class
subgraph field or API response, it'd save every builder doing risk/impact
modeling from re-deriving it the way we did.

## Net assessment

The v3 subgraph and QuoterV2 gave us everything the price-impact half of
this project needed, and cross-checking our own math against the real
contract is what let us trust an extreme result instead of assuming it
was a bug and quietly rounding it away. The friction was entirely in
"which ID is real" and "how do I call this without a JS SDK" -- both
fixable with docs, neither a gap in the protocol itself.
