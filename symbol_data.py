from numpy import NaN
import logging
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import yfinance as yf
import pytz

log = logging.getLogger(__name__)


class SymbolAlreadyInCollectionError(Exception):
    ...


class SymbolError(Exception):
    ...


class SymbolData:
    yf_symbol: str
    interval: str
    bars: pd.DataFrame
    registered_ta_functions: set
    ta_data: dict
    interval_minutes: int
    max_range: relativedelta
    interval_delta: relativedelta
    refresh_timeout: datetime

    class Decorators:
        @classmethod
        def refresh_bars(cls, decorated):
            def inner(*args, **kwargs):
                if kwargs.get("refresh"):
                    args[0].refresh_cache()
                return decorated(*args, **kwargs)

            return inner

    def __init__(self, yf_symbol: str, interval: str = "5m"):
        self.yf_symbol = yf_symbol

        self.interval = interval
        self.registered_ta_functions = set()
        self.ta_data = {}
        self.interval_delta, self.max_range = SymbolData.get_interval_settings(self.interval)
        self.interval_minutes = int(interval[:-1])
        self.refresh_timeout = None

        self.refresh_cache()

        if len(self.bars) == 0:
            # invalid ticker
            error_message = f"Invalid symbol specified, bailing"
            log.error(error_message)
            raise SymbolError(error_message)

    def get_interval_settings(interval):
        minutes_intervals = ["1m", "2m", "5m", "15m", "30m", "60m", "90m"]
        max_period = {
            "1m": 6,
            "2m": 59,
            "5m": 59,
            "15m": 59,
            "30m": 59,
            "60m": 500,
            "90m": 59,
            "1h": 500,
            "1d": 2000,
            "5d": 500,
            "1wk": 500,
            "1mo": 500,
            "3mo": 500,
        }

        if interval in minutes_intervals:
            return (
                relativedelta(minutes=int(interval[:-1])),
                relativedelta(days=max_period[interval]),
            )
        else:
            raise ValueError("I can't be bothered implementing intervals longer than 90m")

    def __repr__(self):
        return self.yf_symbol

    def _validate_minute(self, minute):
        if self.interval == "1m":
            return True
        elif self.interval == "2m":
            if minute % 2 == 0:
                return True
        elif minute % 5 == 0:
            return True
        return False

    @staticmethod
    def merge_bars(bars, new_bars):
        return pd.concat([bars, new_bars[~new_bars.index.isin(bars.index)]]).sort_index()

    def _make_now(self):
        local_tz = pytz.timezone("Australia/Melbourne")
        start_date_unaware = datetime.now()
        start_date_melbourne = local_tz.localize(start_date_unaware)

        # if there's no - then assume its NYSE, else assume its crypto
        if self.yf_symbol.find("-") == -1:
            tz = "US/Eastern"
        else:
            tz = "UTC"

        start_date = start_date_melbourne.astimezone(pytz.timezone(tz))
        start_date = start_date.replace(microsecond=0)
        return start_date

    def refresh_cache(self, start: pd.Timestamp = None, end: pd.Timestamp = None):
        cache_miss = False
        initialising = False

        if not hasattr(self, "bars") or len(self.bars) == 0:
            cache_miss = True
            initialising = True
            log.debug(f"Cache miss - bars len 0")

            rounded_end = self._make_now()
            max_duration = rounded_end - self.max_range
            rounded_start = round_time(max_duration, self.interval_minutes)

            yf_start = rounded_start

            self.bars = pd.DataFrame()

        # has a bars attribute so its safe to inspect it
        else:
            yf_start = self.bars.index[-1]
            if start == None:
                rounded_start = self.bars.index[0]
            else:
                rounded_start = round_time(start, self.interval_minutes)
                if rounded_start < self.bars.index[0]:
                    yf_start = rounded_start
                    cache_miss = True
                    log.debug(f"Cache miss - start earlier than bars")
                elif rounded_start > self.bars.index[-1]:
                    cache_miss = True
                    log.debug(f"Cache miss - start later than bars")

            if end == None:
                rounded_end = round_time(self._make_now(), self.interval_minutes)
            else:
                rounded_end = round_time(end, self.interval_minutes)
            if rounded_end > self.bars.index[-1]:
                cache_miss = True
                log.debug(f"Cache miss - end later than bars")

        if cache_miss:
            if self.refresh_timeout != None and self.refresh_timeout > datetime.now():
                log.debug(
                    f"Cache timeout {self.refresh_timeout} is still in effect, cancelling cache refresh"
                )
                return

            log.debug(f"  - pulling from yf from {yf_start}")
            new_bars = yf.Ticker(self.yf_symbol).history(
                start=yf_start,
                interval=self.interval,
                actions=False,
                debug=False,
            )

            if len(new_bars) == 0:
                log.error(f"Failed to retrieve new bars")
                return

            # yfinance returns results for periods still in progress (eg. includes 9:07:00 after 9:05:00 if you query at 9:08)
            if not self._validate_minute(new_bars.index[-1].minute):
                # trim it
                log.debug(f"  - dropped half-baked row {new_bars.index[-1]}")
                new_bars = new_bars.iloc[:-1]

            if not initialising:
                old_rows = len(self.bars)
                old_start = self.bars.index[0]
                old_finish = self.bars.index[-1]

            self.bars = self.merge_bars(self.bars, new_bars)

            if not initialising:
                log.debug(
                    f"  - merged {old_rows:,} old bars with {len(new_bars):,} new bars, new length is {len(self.bars):,}"
                )
                if self.bars.index[0] != old_start:
                    log.debug(f"  - new start is {self.bars.index[0]} vs old {old_start}")
                if self.bars.index[-1] != old_finish:
                    log.debug(f"  - new finish is {self.bars.index[-1]} vs old {old_finish}")

            self._reapply_btalib(start=new_bars.index[0], end=new_bars.index[-1])

            timeout_seconds = SymbolData.get_pause(self.interval)
            timeout_window = relativedelta(seconds=timeout_seconds)
            new_timeout = datetime.now() + timeout_window
            self.refresh_timeout = new_timeout

    def get_interval_integer(interval):
        if interval in ["1m", "2m", "5m", "15m", "30m"]:
            return int(interval[:-1])

        raise ValueError("I can't be bothered implementing intervals longer than 30m")

    def get_interval_in_seconds(interval):
        interval_int = SymbolData.get_interval_integer(interval)
        seconds = interval_int * 60
        return seconds

    def get_pause(interval):
        interval_seconds = SymbolData.get_interval_in_seconds(interval)

        # get current time
        now = datetime.now()
        # convert it to seconds
        now_ts = now.timestamp()
        # how many seconds into the current 5 minute increment are we
        mod = now_ts % interval_seconds
        # 5 minutes minus that = seconds til next 5 minute mark
        pause = interval_seconds - mod
        # sleep for another 90 seconds - this is the yahoo finance gap
        if interval_seconds >= 300:
            pause += 90
        return pause

    def apply_btalib(self, btalib_function, start=None, end=None):
        key_name = str(btalib_function)
        # new ta function
        if not str(btalib_function) in self.ta_data:
            # register this ta function - so it gets refreshed next time there is a cache miss
            self.ta_data[key_name] = btalib_function(self.bars).df
            self.registered_ta_functions.add(btalib_function)

        else:
            # existing ta function, so just refresh what's changed
            # start by grabbing the new rows, plus a buffer of 100 previous rows
            # get the index 100 rows earlier

            start_loc = self.bars.index.get_loc(start)
            padding = 100
            if start_loc < padding:
                padding_start = self.bars.index[0]
            else:
                padding_start = self.bars.index[start_loc - padding]

            # can't just use slice because get a weird error about comparing different timezones
            # ta_data_input = self.bars.loc[padding_start:end]
            ta_data_input = self.bars.loc[
                (self.bars.index >= padding_start) & (self.bars.index <= end)
            ]

            ta_data_output = btalib_function(ta_data_input).df

            # NOT NEEDED - the xor gets rid of this
            # get rid of the padding
            # ta_data_output_trimmed = ta_data_output.loc[start:end]

            dest_df = self.ta_data[key_name]

            self.ta_data[key_name] = self.merge_bars(dest_df, ta_data_output)
            # pd.concat([dest_df, ta_data_output[~ta_data_output.index.isin(dest_df.index)]]).sort_index()

    def _reapply_btalib(self, start=None, end=None):
        if not start:
            start = self.bars.index[0]
        if not end:
            end = self.bars.index[-1]

        for btalib_function in self.registered_ta_functions:
            self.apply_btalib(btalib_function, start, end)

    def get_first(self):
        return self.bars.iloc[0]

    @Decorators.refresh_bars
    def get_range(self, start: pd.Timestamp = None, end: pd.Timestamp = None):
        return self.bars.loc[start:end]

    @Decorators.refresh_bars
    def get_latest(self, refresh=False):
        return self.bars.iloc[-1]

    @Decorators.refresh_bars
    def in_bars(self, timestamp, refresh=False):
        return timestamp in self.bars


def round_time(date: pd.Timestamp, interval_minutes):
    minutes = (date.minute % interval_minutes) * 60
    seconds = date.second
    total_seconds = minutes + seconds

    interval_seconds = interval_minutes * 60
    interval_midpoint = interval_seconds / 2

    if total_seconds < interval_midpoint:
        # round down
        delta = -relativedelta(seconds=total_seconds)

    else:
        # round up
        padding = interval_seconds - total_seconds
        delta = relativedelta(seconds=padding)

    rounded_date = date + delta
    # log_wp.debug(f"Rounded {date} to {rounded_date}")
    return rounded_date
