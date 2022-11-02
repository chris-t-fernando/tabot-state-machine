from abc import ABC, abstractmethod
from symbol import Symbol, SymbolData, InvalidQuantity, InvalidPrice
from typing import List
from .time_manager import TimeManager
from .play_config import PlayConfig
from parameter_store import Ssm, IParameterStore
import json
from .weather import IWeatherReader, StubWeather
from broker_api import AlpacaAPI, BackTestAPI, ITradeAPI, IOrderResult
from datetime import datetime
import uuid
import logging
from math import floor
from logbeam import CloudWatchLogsHandler
from pythonjsonlogger import jsonlogger
from strategies import MacdPlayConfig

# from strategies.macd import MacdPlayConfig

log = logging.getLogger(__name__)

"""
At a minimum, a Strategy must implement the following interfaces:
    IStateWaiting
    IStateEnteringPosition
    IStateStoppingLoss
    IStateTakingProfit
    IStateTerminated

A Strategy may also choose the extend the following abstracts:
    APlayController

It is possible but unusual for a Strategy to extend the following abstracts (usually if you want to add a new state/remove a state):
    APlayConfig
    APlayTemplate
    APlayInstance
    AInstanceTelemetry
    APlayTelemetry
    AState
"""


# class InstanceTemplate(ABC):
#    def __init__(
#        self,
#        name: str,
#        buy_signal_strength: float,
#        take_profit_risk_multiplier: float,
#        take_profit_pct_to_sell: float,
#        stop_loss_trigger_pct: float,
#        stop_loss_type: str = "market",
#        stop_loss_hold_intervals: int = 1,
#        buy_order_type: str = "limit",
#        buy_timeout_intervals: int = 2,
#    ) -> None:
#        self.name = name
#        self.buy_signal_strength = buy_signal_strength
#        self.buy_order_type = buy_order_type
#        self.take_profit_risk_multiplier = take_profit_risk_multiplier
#        self.take_profit_pct_to_sell = take_profit_pct_to_sell
#        self.stop_loss_trigger_pct = stop_loss_trigger_pct
#        self.stop_loss_type = stop_loss_type
#        self.stop_loss_hold_intervals = stop_loss_hold_intervals
#        self.buy_timeout_intervals = buy_timeout_intervals
#
#    def __repr__(self) -> str:
#        return f"<{type(self).__name__} '{self.name}'>"
