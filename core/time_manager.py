from abc import ABC, abstractmethod
from typing import Set
from symbol import Symbol
import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class TimeManagerNotStartedError(Exception):
    ...


class ITimeManager(ABC):
    back_test: bool = False

    @abstractmethod
    def __init__(self, interval: int = 300) -> None:
        ...

    # @abstractmethod
    def add_symbol(self, symbol: Symbol) -> bool:
        ...

    @abstractmethod
    def add_symbols(self, symbols: set) -> bool:
        ...

    @abstractmethod
    def start(self):
        ...

    @property
    @abstractmethod
    def first(self):
        ...

    @property
    @abstractmethod
    def last(self):
        ...

    @property
    @abstractmethod
    def now(self):
        ...

    @now.setter
    @abstractmethod
    def now(self, new_date):
        ...

    @abstractmethod
    def tick(self):
        ...


class BackTestTimeManager(ITimeManager):
    _symbols: Set[Symbol]
    _date: pd.Timestamp
    tick_padding: int = 90
    now: pd.Timestamp
    first: pd.Timestamp
    last: pd.Timestamp
    tick_ttl: int
    back_test: bool = True

    def __init__(self, interval: int = 300) -> None:
        self._symbols = set()
        self._date = None

        self._interval = interval
        self._delta = relativedelta(seconds=interval)

        self._symbols = set()

    def start(self):
        self.now = self.first

    """
    def add_symbol(self, symbol: Symbol) -> bool:
        return self._symbols.add(symbol)
    """

    def add_symbols(self, symbols: set) -> bool:
        symbol_set = set(symbols)
        self._symbols = self._symbols | symbol_set

    @property
    def first(self) -> pd.Timestamp:
        if len(self._symbols) == 0:
            raise RuntimeError("No symbols added yet")

        earliest = None
        for symbol in self._symbols:
            this_date = symbol.ohlc.get_first().name
            if not earliest:
                earliest = this_date
            elif this_date > earliest:
                earliest = this_date

        # earliest is now the LATEST first record
        # pad it out for SMA etc
        padding = self._interval * 100
        padded_earliest = earliest + relativedelta(seconds=padding)
        return padded_earliest

    @property
    def last(self) -> pd.Timestamp:
        if len(self._symbols) == 0:
            raise RuntimeError("No symbols added yet")

        latest = None
        for symbol in self._symbols:
            symbol.ohlc.refresh_cache()
            this_date = symbol.ohlc.bars.index[-1]
            if not latest:
                latest = this_date
            elif this_date < latest:
                latest = this_date

        return latest

    @property
    def now(self) -> pd.Timestamp:
        if not self._date:
            # hackity hack
            # self._date = next(iter(self._symbols)).ohlc.bars.iloc[-1].name
            raise TimeManagerNotStartedError(
                f"Current date not set. Have you called start() yet?"
            )

        return self._date

    @now.setter
    def now(self, new_date: pd.Timestamp) -> None:
        if new_date < self.first:
            raise KeyError(
                f"New date {new_date} is earlier than earliest date {self.first}"
            )
        if new_date > self.last:
            raise KeyError(f"New date {new_date} is after latest date {self.last}")

        self._date = new_date

    def tick(self) -> pd.Timestamp:
        # TODO raise exception or something if we try to tick in to the future
        self.now = self.now + self._delta
        return self.now

    @property
    def tick_ttl(self) -> int:
        # now + padding is later than latest record, so return 0
        # now + padding is less than latest record
        #  - if we are backtesting, then return 0
        #  - if we are not backtesting, then return now - (last record + 90)
        #    - now 9:46
        #    - last record (9.45 + 90) = 9:47
        #
        #    - now 9:49
        #    -

        # backtest will always return 0 - either we're ready to get a new row, or there will never be any more new rows to get

        if self.now == self.latest:
            raise KeyError(f"Backtesting - already at last row")

        return 0

        padded_last = self.last + timedelta(seconds=self.tick_padding)
        if self.now < padded_last:
            return 0

        now = datetime.utcnow()

        return self.now - self._delta


# a = Symbol("BTC-USD")
# im = TimeManager([a])
# print(im.earliest)

# im.date = im.earliest
# while True:
#    print(f"{im.date} - {a.ohlc.get_range(im.date).Close.iloc[0]}")
#    im.tick()
