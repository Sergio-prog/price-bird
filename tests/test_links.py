from app.alerts.links import build_asset_links, format_links
from app.db.enums import AssetType


class Link:
    kind = "dexscreener"
    url = "https://dexscreener.com/ethereum/0xabc"


class Asset:
    type = AssetType.TOKEN
    symbol = "TEST"
    chain = "ethereum"
    contract_address = "0xabc"
    links = [Link()]


def test_link_builder_adds_safe_defaults() -> None:
    links = build_asset_links(Asset())

    assert "dexscreener" in links
    assert "tradingview" in links
    assert links["gmgn"] == "https://gmgn.ai/eth/token/0xabc"
    assert links["fomo"] == "https://fomo.family/tokens/ethereum/0xabc"
    assert links["coinmarketcap"] == "https://coinmarketcap.com/search/?q=0xabc"


def test_format_links_uses_html_magic_links() -> None:
    links = format_links({"dexscreener": "https://dexscreener.com/ethereum/0xabc"})

    assert links == (
        '<tg-emoji emoji-id="5917923733648973619">🦅</tg-emoji> <a href="https://dexscreener.com/ethereum/0xabc">DexScreener</a>'
    )


def test_link_builder_omits_chain_specific_links_when_unsupported() -> None:
    asset = Asset()
    asset.chain = "unsupported"

    links = build_asset_links(asset)

    assert "gmgn" not in links
    assert "fomo" not in links
    assert "dexscreener" in links
    assert "coinmarketcap" in links


def test_fomo_robinhood_deep_link() -> None:
    asset = Asset()
    asset.chain = "robinhood"
    asset.contract_address = "0x395c45c2e5170ab9d020010dc13214ab73051e18"

    links = build_asset_links(asset)

    assert links["fomo"] == ("https://fomo.family/tokens/robinhood/0x395c45c2e5170ab9d020010dc13214ab73051e18")


def test_nft_collections_get_no_token_links() -> None:
    asset = Asset()
    asset.type = AssetType.NFT_COLLECTION
    asset.symbol = "QUOTRONS404"
    asset.links = []
    asset.chain = "robinhood"
    asset.contract_address = "0x027aca2794e44f24950d81227dcd516ffbb49d6e"

    links = build_asset_links(asset)

    assert not {"dexscreener", "gmgn", "fomo", "coinmarketcap"} & set(links)
