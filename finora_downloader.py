from pathlib import Path
import yfinance as yf
import pandas as pd
from tqdm import tqdm

DATA_DIR = Path("data")
START_DATE = "2010-01-01"
END_DATE = None

DATASETS = {
    "stocks": [
        "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA",
        "JPM", "V", "WMT", "UNH", "MA", "PG", "HD", "BAC"
    ],
    "etfs": [
        "SPY", "QQQ", "VTI", "VOO", "IWM", "DIA", "XLK", "XLF", "XLE"
    ],
    "indices": [
        "^GSPC", "^IXIC", "^DJI", "^RUT", "^VIX", "^NSEI", "^BSESN"
    ],
    "crypto": [
        "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD", "ADA-USD"
    ],
    "forex": [
        "EURUSD=X", "GBPUSD=X", "JPY=X", "INR=X", "AUDUSD=X", "CAD=X"
    ],
    "mutual_funds": [
        "VTSAX", "VFIAX", "SWPPX", "FXAIX"
    ]
}


def ensure_dirs():
    for folder in DATASETS.keys():
        (DATA_DIR / folder).mkdir(parents=True, exist_ok=True)

    for folder in [
        "fundamentals",
        "financials",
        "balance_sheet",
        "cashflow",
        "dividends",
        "splits",
        "metadata"
    ]:
        (DATA_DIR / folder).mkdir(parents=True, exist_ok=True)


def clean_symbol(symbol: str) -> str:
    return (
        symbol.replace("^", "")
        .replace("=", "")
        .replace("-", "_")
        .replace("/", "_")
    )


def save_dataframe(df: pd.DataFrame, path: Path):
    if df is None or df.empty:
        return False

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.reset_index()

    df.columns = [
        str(col).replace(" ", "_").lower()
        for col in df.columns
    ]

    csv_path = path.with_suffix(".csv")
    parquet_path = path.with_suffix(".parquet")

    df.to_csv(csv_path, index=False)
    df.to_parquet(parquet_path, index=False)

    return True


def download_price_data(symbol: str, category: str):
    safe_name = clean_symbol(symbol)
    out_path = DATA_DIR / category / safe_name

    try:
        df = yf.download(
            symbol,
            start=START_DATE,
            end=END_DATE,
            auto_adjust=False,
            progress=False,
            threads=False
        )

        if df.empty:
            print(f"[EMPTY] {symbol}")
            return

        save_dataframe(df, out_path)
        print(f"[OK] {symbol}")

    except Exception as e:
        print(f"[FAILED] {symbol}: {e}")


def download_company_data(symbol: str):
    safe_name = clean_symbol(symbol)

    try:
        ticker = yf.Ticker(symbol)

        info = ticker.info
        if info:
            pd.DataFrame([info]).to_csv(
                DATA_DIR / "fundamentals" / f"{safe_name}.csv",
                index=False
            )

        financials = ticker.financials
        if financials is not None and not financials.empty:
            financials.to_csv(DATA_DIR / "financials" / f"{safe_name}.csv")

        balance_sheet = ticker.balance_sheet
        if balance_sheet is not None and not balance_sheet.empty:
            balance_sheet.to_csv(DATA_DIR / "balance_sheet" / f"{safe_name}.csv")

        cashflow = ticker.cashflow
        if cashflow is not None and not cashflow.empty:
            cashflow.to_csv(DATA_DIR / "cashflow" / f"{safe_name}.csv")

        dividends = ticker.dividends
        if dividends is not None and not dividends.empty:
            dividends.reset_index().to_csv(
                DATA_DIR / "dividends" / f"{safe_name}.csv",
                index=False
            )

        splits = ticker.splits
        if splits is not None and not splits.empty:
            splits.reset_index().to_csv(
                DATA_DIR / "splits" / f"{safe_name}.csv",
                index=False
            )

        print(f"[COMPANY DATA OK] {symbol}")

    except Exception as e:
        print(f"[COMPANY DATA FAILED] {symbol}: {e}")


def build_metadata():
    rows = []

    for category, symbols in DATASETS.items():
        for symbol in symbols:
            rows.append({
                "symbol": symbol,
                "safe_name": clean_symbol(symbol),
                "category": category,
                "source": "Yahoo Finance via yfinance",
                "start_date": START_DATE,
                "end_date": END_DATE or "latest"
            })

    df = pd.DataFrame(rows)
    df.to_csv(DATA_DIR / "metadata" / "dataset_manifest.csv", index=False)


def main():
    ensure_dirs()

    print("\nDownloading price datasets...\n")

    for category, symbols in DATASETS.items():
        for symbol in tqdm(symbols, desc=category):
            download_price_data(symbol, category)

    print("\nDownloading company fundamentals...\n")

    for symbol in tqdm(DATASETS["stocks"], desc="fundamentals"):
        download_company_data(symbol)

    build_metadata()

    print("\nDONE.")
    print("All datasets saved inside the data/ folder.")


if __name__ == "__main__":
    main()