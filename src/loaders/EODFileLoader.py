import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from fast_csv_loader import csv_loader

from .AbstractLoader import AbstractLoader

logger = logging.getLogger(__name__)


class EODFileLoader(AbstractLoader):
    """
    A class to load Daily or higher timeframe data from CSV files.

    Parameters:
    :param config: User config
    :type config: dict
    :param timeframe: daily, weekly or monthly
    :type timeframe: str
    :param end_date: End date upto which date must be returned
    :type end_date: Optional[datetime]
    :param period: Number of lines to return from end_date or end of file

    """

    timeframes = dict(daily="D", weekly="W", monthly="ME", quarterly="QE")

    def __init__(
        self,
        config: dict,
        tf: Optional[str] = None,
        end_date: Optional[datetime] = None,
        period: int = 160,
    ):
        # No need to close method to be called for this Class
        self.closed = True

        self.default_tf = str(config.get("DEFAULT_TF", "daily"))

        if self.default_tf not in self.timeframes:
            valid_values = ", ".join(self.timeframes.keys())

            raise ValueError(f"`DEFAULT_TF` in config must be one of {valid_values}")

        if tf is None:
            tf = self.default_tf

        if tf not in self.timeframes:
            valid_values = ", ".join(self.timeframes.keys())

            raise ValueError(f"Timeframe must be one of {valid_values}")

        self.tf = tf
        self.offset_str = self.timeframes[tf]

        self.end_date = end_date
        self.date_format = config.get("DATE_FORMAT", None)

        self.end_date = end_date

        self.data_path = Path(config["DATA_PATH"]).expanduser()

        self.ohlc_dict = dict(
            Open="first",
            High="max",
            Low="min",
            Close="last",
            Volume="sum",
        )

        self.chunk_size = 1024 * 6

        if tf == self.default_tf:
            self.period = period
        elif tf == "weekly":
            self.period = 7 * period
            self.chunk_size = 1024 * 19
        elif tf == "monthly":
            days = 7 if self.default_tf == "weekly" else 1
            self.period = 30 * period // days
        elif tf == "quarterly":
            self.period = 30 * 3 * period

    def get(self, symbol: str) -> Optional[pd.DataFrame]:
        file = self.data_path / f"{symbol.lower()}.csv"

        if not file.exists():
            logger.warning(f"File not found: {file}")
            return

        if self.tf == "monthly" or self.tf == "quarterly":
            # It is faster to load the entire file for monthly or quarterly
            # considering average size of file
            return self.process_monthly(file, self.end_date)

        try:
            df = csv_loader(
                file,
                period=self.period,
                end_date=self.end_date,
                chunk_size=self.chunk_size,
                date_format=self.date_format,
            )
        except IndexError:
            return
        except Exception as e:
            # Any other error log it with the symbol name
            logger.warning(f"{symbol}: Error loading file - {e!r}")
            return

        if self.end_date:
            df = df.loc[: self.end_date]

        if self.tf == self.default_tf or df.empty:
            return df.iloc[-self.period :]

        df = df.resample(self.offset_str).agg(self.ohlc_dict).dropna()

        return df.iloc[-self.period :]

    def process_monthly(self, file, end_date) -> pd.DataFrame:
        df = pd.read_csv(
            file,
            index_col="Date",
            parse_dates=["Date"],
            date_format=self.date_format,
        )

        if end_date:
            df = df.loc[:end_date].iloc[-self.period :]
        else:
            df = df.iloc[-self.period :]

        df = df.resample(self.offset_str).agg(self.ohlc_dict).dropna()

        assert isinstance(df, pd.DataFrame)

        return df

    def close(self):
        """Not required here as nothing to close"""
        pass
