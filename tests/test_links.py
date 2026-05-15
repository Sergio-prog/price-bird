from app.alerts.links import build_asset_links, format_links


class Link:
    kind = "dexscreener"
    url = "https://dexscreener.com/ethereum/0xabc"


class Asset:
    symbol = "TEST"
    chain = "ethereum"
    contract_address = "0xabc"
    links = [Link()]


def test_link_builder_adds_safe_defaults() -> None:
    links = build_asset_links(Asset())

    assert "dexscreener" in links
    assert "tradingview" in links
    assert "axiom" in links


def test_format_links_uses_html_magic_links() -> None:
    links = format_links({"dexscreener": "https://dexscreener.com/ethereum/0xabc"})

    assert links == '<a href="https://dexscreener.com/ethereum/0xabc">DexScreener</a>'
