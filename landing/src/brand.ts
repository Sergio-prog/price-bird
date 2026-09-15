type Quote = { price: number; unit: string; source: string; sourceUrl: string; chart?: string; mcap?: string };

const binance = (pair: string, mcap: string): Quote => ({
  price: 0,
  unit: "$",
  source: "Binance",
  sourceUrl: `https://www.binance.com/en/trade/${pair}_USDT`,
  chart: `https://www.tradingview.com/symbols/${pair}USDT/`,
  mcap,
});

const opensea = (slug: string, price: number): Quote => ({
  price,
  unit: "ETH",
  source: "OpenSea",
  sourceUrl: `https://opensea.io/collection/${slug}`,
});

const quotes: Record<string, Quote> = {
  BTC: { ...binance("BTC", "$1.25T"), price: 63140 },
  "BTC/USDT": { ...binance("BTC", "$1.25T"), price: 63140 },
  ETH: { ...binance("ETH", "$375B"), price: 3120 },
  SOL: { ...binance("SOL", "$69B"), price: 148 },
  BNB: { ...binance("BNB", "$87B"), price: 590 },
  PEPE: {
    price: 0.0000112,
    unit: "$",
    source: "DexScreener",
    sourceUrl: "https://dexscreener.com/ethereum/0xa43fe16908251ee8ef3a74c7e9eb5c9fd8a3aa0e",
    chart: "https://www.tradingview.com/symbols/PEPEUSD/",
    mcap: "$4.7B",
  },
  MILADY: opensea("milady", 3.4),
  "PUDGY PENGUINS": opensea("pudgypenguins", 12.1),
  PUDGYPENGUINS: opensea("pudgypenguins", 12.1),
  BOREDAPEYACHTCLUB: opensea("boredapeyachtclub", 9.8),
};

const multipliers: Record<string, number> = { k: 1e3, m: 1e6, b: 1e9 };

const rule =
  /^(?:\/alert\s+)?(.+?)\s*(floor)?\s*(?:(\d+(?:\.\d+)?)%|([<>])\s*(\$?)(\d+(?:\.\d+)?)([kmb])?\s*([a-z]{2,5})?)$/i;

function escape(text: string) {
  return text.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] ?? c);
}

function link(label: string, url: string) {
  return `<a href="${url}" target="_blank" rel="noopener">${label}</a>`;
}

function money(value: number, unit: string) {
  const digits = value >= 1000 ? 0 : value >= 1 ? 2 : 8;
  const text = value.toLocaleString("en-US", { maximumFractionDigits: digits });
  return unit === "$" ? `$${text}` : `${text} ${unit}`;
}

function percent(from: number, to: number) {
  const change = ((to - from) / from) * 100;
  const arrow = change >= 0 ? "↑" : "↓";
  const sign = change >= 0 ? "+" : "";
  return `${arrow} ${sign}${change.toFixed(1)}%`;
}

type Parsed = { firedTitle: string; firedHtml: string };

function parse(input: string): Parsed | null {
  const match = rule.exec(input.trim());
  if (!match) return null;
  const [, rawName, floor, pct, op, dollar, num, suffix, rawUnit] = match;
  const name = rawName.trim();
  const key = name.toUpperCase();
  const quote = quotes[key];
  const isNft = Boolean(floor) || quote?.unit === "ETH";
  const symbol = isNft ? name.toLowerCase() : key;
  const unit = dollar ? "$" : rawUnit ? rawUnit.toUpperCase() : quote?.unit ?? (isNft ? "ETH" : "$");
  const source = quote?.source ?? (isNft ? "OpenSea" : "DexScreener");
  const sourceUrl =
    quote?.sourceUrl ??
    (isNft
      ? `https://opensea.io/collection/${encodeURIComponent(symbol.replace(/\s+/g, ""))}`
      : `https://dexscreener.com/search?q=${encodeURIComponent(symbol)}`);
  const chart = quote?.chart ?? (isNft ? null : `https://www.tradingview.com/symbols/${encodeURIComponent(symbol)}USD/`);
  const subject = isNft ? "Floor" : "Price";

  let ruleLine: string;
  let firedPrice: number | null;
  let change: string;

  if (pct) {
    const p = Number(pct);
    ruleLine = `${p}% move up or down`;
    firedPrice = quote ? quote.price * (1 + (p + 0.3) / 100) : null;
    change = `↑ +${(p + 0.3).toFixed(1)}%`;
  } else {
    const threshold = Number(num) * (multipliers[(suffix ?? "").toLowerCase()] ?? 1);
    const above = op === ">";
    ruleLine = `${subject} ${above ? "above" : "below"} ${money(threshold, unit)}`;
    firedPrice = threshold * (above ? 1.004 : 0.996);
    change = quote && quote.unit === unit ? percent(quote.price, firedPrice) : above ? "↑" : "↓";
  }

  const priceLine = firedPrice === null ? "" : `\n${isNft ? "Floor price" : "Price"}: ${money(firedPrice, unit)}`;
  const mcapLine = quote?.mcap && !isNft ? `\nMarket cap: ${quote.mcap}` : "";
  const chartLine = chart ? `\nLinks: ${link("TradingView", chart)}` : "";
  const firedHtml = `Rule: ${escape(ruleLine)}${escape(priceLine)}${escape(mcapLine)}\n\nSource: ${link(escape(source), sourceUrl)}${chartLine}`;
  return { firedTitle: `🔔 ${symbol} ${change}`, firedHtml };
}

const input = document.querySelector<HTMLInputElement>("#rule")!;
const typed = document.querySelector<HTMLElement>("#typed")!;
const result = document.querySelector<HTMLElement>("#result")!;
const firedTitle = document.querySelector<HTMLElement>("#fired-title")!;
const fired = document.querySelector<HTMLElement>("#fired")!;

const errorText = "Couldn't read that rule. Try BTC 10%, ETH > 4000 or milady floor 10%.";

function render(value: string) {
  const parsed = parse(value);
  firedTitle.classList.toggle("text-lime", Boolean(parsed));
  firedTitle.classList.toggle("text-haze", !parsed);
  if (!parsed) {
    firedTitle.textContent = value.trim() === "" ? "Type a rule above." : errorText;
    fired.textContent = "";
    return;
  }
  firedTitle.textContent = parsed.firedTitle;
  fired.innerHTML = parsed.firedHtml;
}

input.addEventListener("input", () => render(input.value));

document.querySelectorAll<HTMLButtonElement>("button[data-rule]").forEach((button) => {
  button.addEventListener("click", () => {
    input.value = button.dataset.rule ?? "";
    render(input.value);
    input.focus();
  });
});

const opening = "BTC 10%";
render(opening);

function finishOpening() {
  typed.hidden = true;
  input.hidden = false;
  input.value = opening;
  result.classList.remove("opacity-0");
}

if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  finishOpening();
} else {
  let i = 0;
  const tick = () => {
    i += 1;
    typed.textContent = opening.slice(0, i);
    if (i < opening.length) {
      setTimeout(tick, 90);
    } else {
      setTimeout(finishOpening, 350);
    }
  };
  setTimeout(tick, 600);
}
