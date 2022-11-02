from symbol import Symbol

import logging

log = logging.getLogger(__name__)


class SymbolData:
    symbols: dict[str, Symbol]

    def __init__(self, symbols: set[str]):
        self.symbols = dict()
        for s in symbols:
            s_obj = self._instantiate_symbol(s)
            self.symbols[s] = s_obj

    def _instantiate_symbol(self, symbol: str) -> bool:
        if symbol in self.symbols:
            log.warning(
                f"Attempted to add symbol {symbol} but it was already instantiated."
            )
            return

        s = Symbol(yf_symbol=symbol)

        return s
