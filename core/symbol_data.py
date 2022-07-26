from symbol import Symbol
from core.time_manager import ITimeManager
import logging

log = logging.getLogger(__name__)


class SymbolData:
    symbols: dict[str, Symbol]
    unique_symbols: set[Symbol]
    _ta_algos: set
    time_manager: ITimeManager

    def __init__(self, symbols: set[str], algos: set, time_manager: ITimeManager):
        self.symbols = dict()
        self._ta_algos = set()
        self.time_manager = time_manager

        # self._back_testing = back_testing

        for s in symbols:
            s_obj = self._instantiate_symbol(s)
            self.symbols[s] = s_obj

        for a in algos:
            self.register_ta(a)

    def _instantiate_symbol(self, symbol: str) -> bool:
        if symbol in self.symbols:
            log.warning(
                f"Attempted to add symbol {symbol} but it was already instantiated."
            )
            return

        s = Symbol(yf_symbol=symbol, time_manager=self.time_manager)

        return s

    def register_ta(self, ta_algo):
        self._ta_algos.add(ta_algo)
        self._apply_ta()

    def _apply_ta(self):
        for a in self._ta_algos:
            for s_str in self.symbols:
                self.symbols[s_str].ohlc.apply_ta(a)
                # s_obj.ohlc.apply_ta(a)

    @property
    def unique_symbols(self):
        symbol_set = set()
        for k, s in self.symbols.items():
            symbol_set.add(s)

        return symbol_set
