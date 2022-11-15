from symbol import Symbol
from broker_api import ITradeAPI
from .play_config import PlayConfig
from .symbol_handler import SymbolHandler
from .time_manager import BackTestTimeManager


class CategoryHandler:
    """
    1:m symbols, 1:m play configs, 1:1 weather
    Handles the symbols that belong to one category that will have 1:m play_configs applied
    Role is to enumerate play_configs to instantiate SymbolHandlers
    """

    symbols: list[Symbol]
    play_configs: list[PlayConfig]
    symbol_handlers: list[SymbolHandler]
    broker: ITradeAPI
    time_manager: BackTestTimeManager

    def __init__(
        self,
        symbols: set[Symbol],
        play_configs: list[PlayConfig],
        broker: ITradeAPI,
        time_manager: BackTestTimeManager,
    ):
        self.symbols = symbols
        self.play_configs = play_configs
        self.symbol_handlers = []
        self.broker = broker
        self.time_manager = time_manager

        for config in play_configs:
            self.symbol_handlers.append(
                SymbolHandler(
                    symbols=symbols,
                    play_config=config,
                    broker=broker,
                    time_manager=time_manager,
                )
            )

    def start(self):
        for h in self.symbol_handlers:
            h.start()

    def stop(self) -> None:
        for h in self.symbol_handlers:
            h.stop()

    def run(self) -> None:
        for h in self.symbol_handlers:
            h.run()
