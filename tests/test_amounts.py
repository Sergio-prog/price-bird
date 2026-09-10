from decimal import Decimal

import pytest

from app.utils.amounts import parse_amount, resolve_currency
from app.utils.currency import canonical_symbol, chain_native_symbol, native_symbol_or_none


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0.023", (Decimal("0.023"), None)),
        ("$0.023", (Decimal("0.023"), "USD")),
        ("0.023$", (Decimal("0.023"), "USD")),
        ("23m", (Decimal("23000000"), None)),
        ("23M$", (Decimal("23000000"), "USD")),
        ("$1.5b", (Decimal("1500000000"), "USD")),
        ("100k usd", (Decimal("100000"), "USD")),
        ("1,000,000", (Decimal("1000000"), None)),
        ("1.2 ETH", (Decimal("1.2"), "ETH")),
        ("1.2eth", (Decimal("1.2"), "ETH")),
        ("0.5 weth", (Decimal("0.5"), "ETH")),
        ("2k SOL", (Decimal("2000"), "SOL")),
        ("15 usdc", (Decimal("15"), "USD")),
    ],
)
def test_parse_amount(text: str, expected: tuple) -> None:
    assert parse_amount(text) == expected


@pytest.mark.parametrize("text", ["", "abc", "$1 eth", "0", "-5", "1..2", "5 lightyears$"])
def test_parse_amount_rejects_invalid(text: str) -> None:
    with pytest.raises(ValueError):
        parse_amount(text)


def test_resolve_currency() -> None:
    assert resolve_currency(None, default="ETH", native_symbol="ETH") == "ETH"
    assert resolve_currency("USD", default="ETH", native_symbol="ETH") == "USD"
    assert resolve_currency("ETH", default="USD", native_symbol="WETH") == "ETH"
    with pytest.raises(ValueError, match="USD or SOL, not ETH"):
        resolve_currency("ETH", default="USD", native_symbol="SOL")
    with pytest.raises(ValueError, match="priced in USD, not ETH"):
        resolve_currency("ETH", default="USD", native_symbol=None)


def test_currency_helpers() -> None:
    assert canonical_symbol("weth") == "ETH"
    assert canonical_symbol("usdt") == "USD"
    assert native_symbol_or_none("USDC") is None
    assert native_symbol_or_none("SOL") == "SOL"
    assert chain_native_symbol("solana") == "SOL"
    assert chain_native_symbol("unknown") is None
