from abc import ABC, abstractmethod
from symbol import Symbol
from .symbol_data import SymbolData
from .play_config import PlayConfig
from broker_api import ITradeAPI
import logging


class State(ABC):

    __tabot_strategy__: bool = True

    STATE_STAY = 0
    STATE_SPLIT = 1
    STATE_MOVE = 2

    symbol: Symbol
    symbol_str: str
    ohlc: SymbolData
    config: PlayConfig
    broker: ITradeAPI
    log: logging.Logger

    @abstractmethod
    def __init__(self, previous_state, parent_instance=None) -> None:
        self.previous_state = previous_state
        if not parent_instance:
            self.parent_instance = previous_state.parent_instance
            config_source = previous_state
        else:
            self.parent_instance = parent_instance
            config_source = parent_instance

        self.symbol = config_source.symbol
        self.symbol_str = config_source.symbol_str
        self.ohlc = config_source.symbol.ohlc
        self.config = config_source.config
        self.controller = self.parent_instance.parent_controller
        self.log = self.parent_instance.log

        self.log.debug(f"Started {self.__repr__()}")

    @abstractmethod
    def check_exit(self):
        self.log.log(9, f"Started check_exit on {self.__repr__()}")
        # log.log(9, f"Started check_exit on {self.__repr__()}")

    def do_exit(self):
        self.log.log(9, f"Finished do_exit on {self.__repr__()}")

    def __del__(self):
        # use this to make sure that open orders are cancelled?
        self.log.log(9, f"Deleting {self.__repr__()}")

    def __repr__(self) -> str:
        return self.__class__.__name__
