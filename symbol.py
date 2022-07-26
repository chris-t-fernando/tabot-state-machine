from symbol_data import SymbolData
import logging

log = logging.getLogger(__name__)


class Symbol:
    def __init__(
        self,
        yf_symbol: str,
        alp_symbol: str,
        min_quantity_increment: float = 1,
        min_quantity: float = 1,
        min_price_increment: float = 0.001,
        interval="5m",
    ) -> None:
        self.yf_symbol = yf_symbol
        self.alp_symbol = alp_symbol
        self.min_quantity_increment = min_quantity_increment
        self.min_quantity = min_quantity
        self.min_price_increment = min_price_increment
        self.interval = interval
        self.data = SymbolData(yf_symbol=yf_symbol, interval=interval)

    def __repr__(self) -> str:
        return self.yf_symbol
