from typing import Set
from core.abstracts import Symbol
from pandas import Timestamp
from dateutil.relativedelta import relativedelta


class TimeManager:
    def __init__(self, symbol_list: list = None, interval: int = 300) -> None:
        self._symbols: Set[Symbol]
        self._symbols = set()

        self._date: Timestamp
        self._date = None

        self._interval = interval
        self._delta = relativedelta(seconds=interval)

        if symbol_list:
            self.add_symbols(symbol_list)

    def add_symbol(self, symbol: Symbol) -> bool:
        return self._symbols.add(symbol)

    def add_symbols(self, symbol_list: list) -> bool:
        symbol_set = set(symbol_list)
        self._symbols = self._symbols | symbol_set

    @property
    def first(self):
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
    def last(self):
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
    def now(self):
        if not self._date:
            # hackity hack
            self._date = next(iter(self._symbols)).ohlc.bars.iloc[-1].name

        return self._date

    @now.setter
    def now(self, new_date):
        if new_date < self.first:
            raise KeyError(f"New date {new_date} is earlier than earliest date {self.first}")
        if new_date > self.last:
            raise KeyError(f"New date {new_date} is after latest date {self.last}")

        self._date = new_date

    def tick(self):
        self.now = self.now + self._delta
        return self.now


# a = Symbol("BTC-USD")
# im = TimeManager([a])
# print(im.earliest)

# im.date = im.earliest
# while True:
#    print(f"{im.date} - {a.ohlc.get_range(im.date).Close.iloc[0]}")
#    im.tick()
