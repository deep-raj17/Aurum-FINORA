from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yfinance as yf

LOGGER = logging.getLogger("finora.yahoo_loader")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


@dataclass
class YahooLoaderConfig:
    project_root: Path = Path(__file__).resolve().parents[2]
    tickers_file: Path = project_root / "src" / "config" / "tickers.json"
    data_root: Path = project_root / "data" / "raw" / "yahoo"
    start_date: str = "2010-01-01"
    end_date: str | None = None
    interval: str = "1d"
    sleep_seconds: float = 0.5
    save_csv: bool = True
    save_parquet: bool = True


class YahooFinanceLoader:
    def __init__(self, config: YahooLoaderConfig | None = None):
        self.config = config or YahooLoaderConfig()
        self.config.data_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_symbol(symbol: str) -> str:
        return (
            symbol.replace("^", "")
            .replace("=", "")
            .replace("-", "_")
            .replace("/", "_")
            .replace(".", "_")
        )

    @staticmethod
    def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.reset_index()

        df.columns = [
            str(col).strip().replace(" ", "_").replace("-", "_").lower() for col in df.columns
        ]

        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")

        return df

    def load_tickers(self) -> dict[str, list[str]]:
        if not self.config.tickers_file.exists():
            raise FileNotFoundError(f"Missing tickers file: {self.config.tickers_file}")

        with open(self.config.tickers_file, encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError("tickers.json must contain a JSON object.")

        return data

    def _save(self, df: pd.DataFrame, category: str, symbol: str) -> None:
        safe = self._safe_symbol(symbol)
        out_dir = self.config.data_root / category
        out_dir.mkdir(parents=True, exist_ok=True)

        if self.config.save_csv:
            df.to_csv(out_dir / f"{safe}.csv", index=False)

        if self.config.save_parquet:
            df.to_parquet(out_dir / f"{safe}.parquet", index=False)

    def download_price_history(self, symbol: str, category: str) -> pd.DataFrame | None:
        try:
            LOGGER.info("Downloading %s [%s]", symbol, category)

            df = yf.download(
                tickers=symbol,
                start=self.config.start_date,
                end=self.config.end_date,
                interval=self.config.interval,
                auto_adjust=False,
                progress=False,
                threads=False,
            )

            df = self._clean_columns(df)

            if df.empty:
                LOGGER.warning("Empty dataset: %s", symbol)
                return None

            df["symbol"] = symbol
            df["category"] = category
            df["source"] = "yahoo_finance"

            self._save(df, category, symbol)

            LOGGER.info("Saved %s rows for %s", len(df), symbol)
            return df

        except Exception as exc:
            LOGGER.exception("Failed downloading %s: %s", symbol, exc)
            return None

    def download_all_prices(self) -> None:
        tickers = self.load_tickers()

        manifest = []

        for category, symbols in tickers.items():
            if not isinstance(symbols, list):
                LOGGER.warning("Skipping invalid category: %s", category)
                continue

            for symbol in symbols:
                df = self.download_price_history(symbol, category)

                manifest.append(
                    {
                        "symbol": symbol,
                        "category": category,
                        "status": "ok" if df is not None else "failed",
                        "rows": 0 if df is None else len(df),
                        "start_date": self.config.start_date,
                        "end_date": self.config.end_date or "latest",
                        "interval": self.config.interval,
                    }
                )

                time.sleep(self.config.sleep_seconds)

        manifest_df = pd.DataFrame(manifest)
        manifest_dir = self.config.data_root / "_manifest"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_df.to_csv(manifest_dir / "yahoo_manifest.csv", index=False)
        manifest_df.to_parquet(manifest_dir / "yahoo_manifest.parquet", index=False)

        LOGGER.info("Manifest saved.")

    def download_company_fundamentals(self, symbols: list[str]) -> None:
        out_root = self.config.data_root / "fundamentals"
        out_root.mkdir(parents=True, exist_ok=True)

        for symbol in symbols:
            safe = self._safe_symbol(symbol)

            try:
                LOGGER.info("Downloading fundamentals: %s", symbol)

                ticker = yf.Ticker(symbol)
                info = ticker.info or {}

                if info:
                    pd.DataFrame([info]).to_csv(out_root / f"{safe}_info.csv", index=False)

                financials = ticker.financials
                if financials is not None and not financials.empty:
                    financials.to_csv(out_root / f"{safe}_financials.csv")

                balance_sheet = ticker.balance_sheet
                if balance_sheet is not None and not balance_sheet.empty:
                    balance_sheet.to_csv(out_root / f"{safe}_balance_sheet.csv")

                cashflow = ticker.cashflow
                if cashflow is not None and not cashflow.empty:
                    cashflow.to_csv(out_root / f"{safe}_cashflow.csv")

                dividends = ticker.dividends
                if dividends is not None and not dividends.empty:
                    dividends.reset_index().to_csv(out_root / f"{safe}_dividends.csv", index=False)

                splits = ticker.splits
                if splits is not None and not splits.empty:
                    splits.reset_index().to_csv(out_root / f"{safe}_splits.csv", index=False)

                LOGGER.info("Saved fundamentals: %s", symbol)

            except Exception as exc:
                LOGGER.exception("Fundamentals failed for %s: %s", symbol, exc)

            time.sleep(self.config.sleep_seconds)

    def run_full_yahoo_ingestion(self) -> None:
        tickers = self.load_tickers()
        self.download_all_prices()

        stock_symbols = tickers.get("stocks", [])
        if stock_symbols:
            self.download_company_fundamentals(stock_symbols)


def main() -> None:
    loader = YahooFinanceLoader()
    loader.run_full_yahoo_ingestion()


if __name__ == "__main__":
    main()
