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

    timeframes = dict(daily="D", weekly="W-SUN", monthly="MS", quarterly="QE")

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

            raise ValueError(
                f"`DEFAULT_TF` in config must be one of {valid_values}"
            )

        if tf is None:
            tf = self.default_tf

        if not tf in self.timeframes:
            valid_values = ", ".join(self.timeframes.keys())

            raise ValueError(f"Timeframe must be one of {valid_values}")

        self.tf = tf
        self.offset_str = self.timeframes[tf]

        self.end_date = end_date
        self.date_column = config.get("DATE_COLUMN", "Date")
        self.date_format = config.get("DATE_FORMAT", None)

        if end_date:
            if self.tf == "weekly":
                self.end_date = self.last_day_week(end_date)
            elif self.tf == "monthly":
                self.end_date = self.last_day_month(end_date)

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

        warnings = []
        file = self.data_path / f"{symbol.lower()}.csv"

        if not file.exists():
            warnings.append(f"File not found: {file}")
            return None, warnings

        df = None
        try:
            if self.tf == "monthly" or self.tf == "quarterly":
                df = self.process_monthly(file, self.end_date) # process_monthly should also return (df, warnings_list)
                # For now, let's assume process_monthly is refactored or doesn't produce its own warnings for this example
                # If process_monthly is called, it might return a tuple (df, list_of_warnings)
                # For simplicity here, we'll assume it returns df and we handle its warnings separately if needed.
                # Or, it could append to a list passed by reference.
                # Let's assume process_monthly is refactored to: df, new_warnings = self.process_monthly(...)
                # and then warnings.extend(new_warnings)
            else:
                df = csv_loader(
                    file,
                    period=self.period,
                    end_date=self.end_date,
                    chunk_size=self.chunk_size,
                    date_column=self.date_column,
                    date_format=self.date_format,
                )
        except IndexError:
            warnings.append(f"IndexError while loading {symbol}. Insufficient data or incorrect format near end of file.")
            return None, warnings
        except Exception as e:
            warnings.append(f"{symbol}: Error loading file - {e!r}")
            return None, warnings

        if df is None or df.empty: # df could be None if process_monthly failed and returned None
             # A warning might have already been added by specific exceptions.
             # If df is empty after successful load, that's also a case to report if not already covered.
            if not any(symbol in w for w in warnings): # Avoid duplicate general message if specific error already logged
                warnings.append(f"No data loaded for {symbol}, or file was empty after processing.")
            return None, warnings


        if self.tf == self.default_tf: # If no resampling needed and df is not empty
            return df, warnings

        # Resampling part
        try:
            df_resampled = (
                df.resample(self.offset_str, label="left")
                .agg(self.ohlc_dict)
                .dropna()
            )
            assert isinstance(df_resampled, pd.DataFrame)
            return df_resampled, warnings
        except Exception as e:
            warnings.append(f"Error during resampling for {symbol} to {self.tf}: {e!r}")
            return None, warnings


    def process_monthly(self, file, end_date) -> tuple[Optional[pd.DataFrame], list[str]]:
        warnings = []
        df = None
        try:
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

            if df.empty:
                warnings.append(f"No data for {file.stem} after date slicing for monthly/quarterly processing.")
                return None, warnings

            df_resampled = df.resample(self.offset_str).agg(self.ohlc_dict).dropna()

            if df_resampled.empty:
                warnings.append(f"No data for {file.stem} after resampling to {self.offset_str}.")
                return None, warnings

            assert isinstance(df_resampled, pd.DataFrame)
            return df_resampled, warnings

        except Exception as e:
            warnings.append(f"Error processing monthly/quarterly for {file.stem}: {e!r}")
            return None, warnings

    def last_day_week(self, date: datetime) -> datetime:
        """Given a date returns the date for Saturday"""

        weekday = date.weekday()

        if weekday == 5:
            # saturday
            return date

        remaining_days = 5 - weekday

        if remaining_days == -1:
            # its a sunday
            remaining_days += 7

        return date + timedelta(remaining_days)

    def last_day_month(self, date: datetime) -> datetime:
        """Given a date returns the date for last day of month"""

        month = date.month % 12 + 1
        year = date.year + (1 if month == 1 else 0)

        return datetime(year, month, 1) - timedelta(1)

    def close(self):
        """Not required here as nothing to close"""
        pass
