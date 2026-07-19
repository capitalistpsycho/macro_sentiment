"""
Central ticker registry for the Macro Compass.

Every ticker the dashboard tracks lives here with display metadata so the data
layer and the pages share one source of truth. Groups map to the dashboard
pages; ``ALL_TICKERS`` is the de-duplicated download list used by run_macro.
"""

from __future__ import annotations

# ── (ticker, label, currency) tuples grouped by domain ────────────────────────

EQUITY_BENCHMARKS = [
    ("^GSPTSE", "S&P/TSX Composite", "CAD"),
    ("^GSPC",   "S&P 500",           "USD"),
    ("^IXIC",   "NASDAQ Composite",  "USD"),
    ("^RUT",    "Russell 2000",      "USD"),
    ("^VIX",    "VIX",               "USD"),
    ("XIU.TO",  "TSX 60",            "CAD"),
    ("XIC.TO",  "TSX Composite ETF", "CAD"),
    ("SPY",     "S&P 500 ETF",       "USD"),
    ("QQQ",     "NASDAQ 100 ETF",    "USD"),
    ("IWM",     "Russell 2000 ETF",  "USD"),
    ("DIA",     "Dow Jones ETF",     "USD"),
    ("RSP",     "S&P 500 Equal Wt",  "USD"),
]

STYLE_FACTOR = [
    ("IWF",    "US Large Growth",   "USD"),
    ("IWD",    "US Large Value",    "USD"),
    ("MTUM",   "US Momentum",       "USD"),
    ("USMV",   "US Low Volatility", "USD"),
    ("QUAL",   "US Quality",        "USD"),
    ("IWB",    "US Large Blend",    "USD"),
    ("ZLB.TO", "CA Low Volatility", "CAD"),
    ("XMD.TO", "CA Mid Cap",        "CAD"),
]

SECTOR_US = [
    ("XLK",  "Technology",         "USD"),
    ("XLF",  "Financials",         "USD"),
    ("XLE",  "Energy",             "USD"),
    ("XLV",  "Health Care",        "USD"),
    ("XLI",  "Industrials",        "USD"),
    ("XLY",  "Consumer Disc.",     "USD"),
    ("XLP",  "Consumer Staples",   "USD"),
    ("XLU",  "Utilities",          "USD"),
    ("XLRE", "Real Estate",        "USD"),
    ("XLB",  "Materials",          "USD"),
    ("XLC",  "Communications",     "USD"),
]

SECTOR_CA = [
    ("XEG.TO", "Energy",       "CAD"),
    ("XFN.TO", "Financials",   "CAD"),
    ("XIT.TO", "Technology",   "CAD"),
    ("XMA.TO", "Materials",    "CAD"),
    ("XRE.TO", "REITs",        "CAD"),
    ("ZUH.TO", "Health Care",  "CAD"),
]

REGIONAL = [
    ("EEM",    "Emerging Markets", "USD"),
    ("VEA",    "Developed ex-US",  "USD"),
    ("VGK",    "Europe",           "USD"),
    ("EWJ",    "Japan",            "USD"),
    ("MCHI",   "China",            "USD"),
    ("EWC",    "Canada (USD)",     "USD"),
    ("HXX.TO", "Europe (CAD)",     "CAD"),
    ("CJP.NE", "Japan Hedged",     "CAD"),
]

FIXED_INCOME = [
    ("^TNX",   "US 10Y Yield",      "USD"),
    ("^IRX",   "US 3M Yield",       "USD"),
    ("^FVX",   "US 5Y Yield",       "USD"),
    ("^TYX",   "US 30Y Yield",      "USD"),
    ("^MOVE",  "MOVE (rate vol)",   "USD"),
    ("TLT",    "Long Duration",     "USD"),
    ("IEF",    "Medium Duration",   "USD"),
    ("SHY",    "Short Duration",    "USD"),
    ("HYG",    "High Yield",        "USD"),
    ("LQD",    "Investment Grade",  "USD"),
    ("TIP",    "TIPS",              "USD"),
    ("ZAG.TO", "CA Aggregate Bond", "CAD"),
    ("XBB.TO", "CA Bond",           "CAD"),
]

COMMODITIES = [
    ("GC=F", "Gold",          "USD"),
    ("CL=F", "WTI Crude",     "USD"),
    ("HG=F", "Copper",        "USD"),
    ("SI=F", "Silver",        "USD"),
    ("NG=F", "Natural Gas",   "USD"),
    ("ZW=F", "Wheat",         "USD"),
    ("GLD",  "Gold ETF",      "USD"),
    ("USO",  "Oil ETF",       "USD"),
    ("COPX", "Copper Miners", "USD"),
    ("DJP",  "Broad Commod.", "USD"),
    # Uranium — no clean spot future on yfinance; SPUT tracks physical spot,
    # the ETFs/Cameco track the equity complex.
    ("U-UN.TO", "Uranium (SPUT spot)", "CAD"),
    ("URA",  "Uranium Miners",   "USD"),
    ("URNM", "Uranium Pure-Play", "USD"),
    ("CCJ",  "Cameco",           "USD"),
]

# ── Sector → industry-group ETFs (drilldown on the Sectors page) ──────────────
# Maps each US sector SPDR to the liquid industry ETFs that sit beneath it.
INDUSTRY_GROUPS: dict[str, list[tuple[str, str]]] = {
    "XLK":  [("SMH", "Semiconductors"), ("IGV", "Software"),
             ("SKYY", "Cloud"), ("CIBR", "Cybersecurity")],
    "XLF":  [("KRE", "Regional Banks"), ("KBE", "Banks"),
             ("IAI", "Broker-Dealers"), ("KIE", "Insurance")],
    "XLE":  [("XOP", "Oil & Gas E&P"), ("OIH", "Oil Services"),
             ("AMLP", "Midstream / MLPs")],
    "XLV":  [("IBB", "Biotech"), ("IHI", "Medical Devices"), ("IHF", "Providers")],
    "XLI":  [("ITA", "Aerospace & Defense"), ("IYT", "Transports"), ("JETS", "Airlines")],
    "XLY":  [("XRT", "Retail"), ("XHB", "Homebuilders")],
    "XLB":  [("GDX", "Gold Miners"), ("COPX", "Copper Miners"),
             ("LIT", "Lithium"), ("MOO", "Agribusiness")],
}

# Flat (ticker, label, ccy) list so the industry ETFs get downloaded like any
# other group. Built from INDUSTRY_GROUPS to keep one source of truth.
SECTOR_INDUSTRY = [
    (tk, lbl, "USD")
    for etfs in INDUSTRY_GROUPS.values()
    for tk, lbl in etfs
]

FX = [
    ("CADUSD=X", "CAD/USD",   "USD"),
    ("EURUSD=X", "EUR/USD",   "USD"),
    ("GBPUSD=X", "GBP/USD",   "USD"),
    ("JPYUSD=X", "JPY/USD",   "USD"),
    ("DX-Y.NYB", "USD Index", "USD"),
]

GROUPS = {
    "equity":          EQUITY_BENCHMARKS,
    "style":           STYLE_FACTOR,
    "sector_us":       SECTOR_US,
    "sector_ca":       SECTOR_CA,
    "sector_industry": SECTOR_INDUSTRY,
    "regional":        REGIONAL,
    "fixed_income":    FIXED_INCOME,
    "commodities":     COMMODITIES,
    "fx":              FX,
}

# ── Lookups ───────────────────────────────────────────────────────────────────

_ALL = []
for _grp in GROUPS.values():
    _ALL.extend(_grp)

ALL_TICKERS: list[str] = list(dict.fromkeys(t for t, _, _ in _ALL))

LABELS: dict[str, str]   = {t: lbl for t, lbl, _ in _ALL}
CURRENCY: dict[str, str] = {t: ccy for t, _, ccy in _ALL}

# Yield tickers quoted as a rate (need normalization, not a price level)
YIELD_TICKERS = {"^TNX", "^IRX", "^FVX", "^TYX"}


def label(ticker: str) -> str:
    return LABELS.get(ticker, ticker)


def currency(ticker: str) -> str:
    return CURRENCY.get(ticker, "USD")
