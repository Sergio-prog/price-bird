# Provider rate limits

Verified against official docs on 2026-09-15. Re-check before relying on a number; providers change limits without notice.

## Binance (via ccxt)

Source: [limits](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/limits), [market data weights](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints)

- Budget: 6000 request weight per minute, enforced per IP, not per API key.
- 429 means back off and honor `Retry-After`. Repeated 429s or ignoring them returns 418 and an IP ban that scales from 2 minutes to 3 days for repeat offenders.
- Weights:

| Endpoint | 1 symbol | symbols list | all symbols |
|---|---|---|---|
| `GET /api/v3/ticker/price` | 2 | 4 | 4 |
| `GET /api/v3/ticker/bookTicker` | 2 | 4 | 4 |
| `GET /api/v3/ticker/24hr` | 2 | 2 (1-20), 40 (21-100), 80 (101+) | 80 |
| `GET /api/v3/exchangeInfo` | 20 | | |

- ccxt calls `load_markets` (`exchangeInfo`, weight 20) on every fresh exchange instance before `fetch_ticker`. Reuse one instance per process and refresh markets on a timer.
- Cheapest full refresh: one all-symbols `ticker/price` call, weight 4, covers every watched CEX pair.

## DexScreener

Source: [reference](https://docs.dexscreener.com/api/reference), [API terms](https://docs.dexscreener.com/api/api-terms-and-conditions)

- No API keys. Limits are enforced per IP.
- 300 requests per minute for `/latest/dex/search`, `/latest/dex/tokens/*`, `/latest/dex/pairs/*`, `/tokens/v1/*`, `/token-pairs/v1/*`.
- 60 requests per minute for token profiles, boosts, ads, community takeovers and metas.
- `/tokens/v1/{chainId}/{tokenAddresses}` and `/latest/dex/tokens/{tokenAddresses}` accept up to 30 comma-separated addresses per request.
- `/latest/dex/pairs/{chainId}/{pairAddresses}` takes up to 30 pool addresses; it prices alerts created from a pasted pool address.
- Search and price polling share the same 300/min pool.
- Terms allow commercial use but forbid building a product whose primary purpose competes with DEX Screener, and forbid reselling the API.

## Hyperliquid

Source: [rate limits](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits). Verified 2026-09-19.

- No API keys. 1200 request weight per minute per IP across all REST calls.
- `spotMetaAndAssetCtxs` and `metaAndAssetCtxs` cost 20 each and return every spot or perp market, so one refresh is at most two requests regardless of how many assets are watched. A search costs the same two requests.

## OpenSea

Source: [API keys](https://docs.opensea.io/reference/api-keys), [API overview](https://docs.opensea.io/reference/api-overview)

- Token bucket per account. All keys on one account share a single bucket, so extra keys do not add capacity. Proxies do not help.
- Free tier: 600 reads per hour and 30 writes per hour. Higher throughput requires contacting OpenSea.
- Response headers expose `X-RateLimit-Limit`, `X-RateLimit-Remaining` and `X-RateLimit-Reset`.
- Keys expire. 401/403 means the key needs renewal.
- Name search (`/api/v2/search`) runs across all chains. Results carry no chain or contract, so the chain is only known after a collection read.
- A pasted NFT contract address costs up to 11 reads: `/api/v2/chain/{chain}/contract/{address}` is tried on `OPENSEA_CHAIN`, then ethereum, base, robinhood, abstract, ape_chain, hyperevm, monad, arbitrum, polygon and optimism, stopping at the first hit, followed by one collection read.
- Every endpoint needs a valid key. Keyless requests return 401 unless a CDN copy happens to be cached, so do not rely on them (checked 2026-09-20).
- Floors are converted with the currency in `floor_price_symbol` (ETH, SOL, POL, ...), not a fixed ETH rate.

## Reservoir

Not verified. The public API was sunset and only works with a pre-existing working key. Treat it as optional.

## Load at the 10-second refresh interval

| Provider | Requests per refresh | Per minute with 200 watched assets |
|---|---|---|
| Binance | 1 per 20 pairs, weight 2 | 60 requests, 120 weight of 6000 |
| DexScreener | 1 per 30 tokens on the same chain | up to ~90 of the 240 budget, worst case spread across chains |
| Hyperliquid | 2 (spot and perps), reused for 2 seconds | 12 of the 40 budget |
| OpenSea | unchanged, NFT floors refresh every 5 minutes | |

## Client-side budgets

The worker never sends at the published limit. Defaults live in `app/core/config.py`:

| Setting | Default | Published limit |
|---|---|---|
| `CCXT_REQUESTS_PER_MINUTE` | 600 | 6000 weight/min; a 20-symbol ticker batch costs 2 |
| `CCXT_MARKETS_TTL_SECONDS` | 3600 | `exchangeInfo` costs 20, so markets are cached |
| `DEXSCREENER_REQUESTS_PER_MINUTE` | 240 | 300/min shared with search |
| `HYPERLIQUID_REQUESTS_PER_MINUTE` | 40 | 1200 weight/min; every request costs 20, so 60/min |
| `PRICE_REFRESH_INTERVAL_SECONDS` | 10 | token and CEX refresh cadence |
| `OPENSEA_READS_PER_HOUR` | 540 | 600/h on a free key |
| `NFT_REFRESH_INTERVAL_SECONDS` | 300 | keeps ~100 collections inside the OpenSea budget |
| `SEARCH_CACHE_SECONDS` | 120 | repeated user searches do not hit providers |

Each throttle allows a burst of one fifth of its per-minute rate, then refills continuously. OpenSea is the exception
with a burst of 10, so a contract lookup does not wait ~7s per chain; the hourly average stays at the budget. A 429 pauses only that
provider for the `Retry-After` value; a Binance 418 pauses ccxt until the ban timestamp in the error message.

## Getting a better OpenSea key

Instant keys from `POST https://api.opensea.io/api/v2/auth/keys` need no account but expire after 7 days at 600 reads/h.
A standard key is free: opensea.io Settings > Developer, verify a non-anonymous email, describe the use case, pass the
captcha, then create the key. Up to three keys per account, all sharing one bucket. Higher throughput requires contacting
OpenSea through the `upgrade_url` returned with an instant key.
