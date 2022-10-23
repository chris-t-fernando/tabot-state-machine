from abc import ABC, abstractmethod
from core import TimeManager
from parameter_store import Ssm, IParameterStore
from core import TimeManager, State
from typing import Set, TypedDict
from symbol import Symbol
from strategies.macd import (
    MacdStateEnteringPosition,
    MacdStateStoppingLoss,
    MacdStateTakingProfit,
    MacdStateWaiting,
    MacdStateTerminated,
    MacdTA,
    MacdInstanceTemplate,
)
import json


class PlayItem:
    category: str
    conditions: str
    max_play_size: float
    buy_timeout_intervals: int
    buy_order_type: str
    take_profit_risk_multiplier: float
    take_profit_pct_to_sell: float
    stop_loss_type: str
    stop_loss_trigger_pct: float
    stop_loss_hold_intervals: int
    state_waiting: State
    state_entering_position: State
    state_taking_profit: State
    state_stopping_loss: State
    state_terminated: State

    def __init__(
        self,
        category: str,
        conditions: str,
        max_play_size: float,
        buy_timeout_intervals: int,
        buy_order_type: str,
        take_profit_risk_multiplier: float,
        take_profit_pct_to_sell: float,
        stop_loss_type: str,
        stop_loss_trigger_pct: float,
        stop_loss_hold_intervals: int,
        state_waiting: State,
        state_entering_position: State,
        state_taking_profit: State,
        state_stopping_loss: State,
        state_terminated: State,
    ) -> None:

        self.category = category
        self.conditions = conditions
        self.max_play_size = max_play_size
        self.buy_timeout_intervals = buy_timeout_intervals
        self.buy_order_type = buy_order_type
        self.take_profit_risk_multiplier = take_profit_risk_multiplier
        self.take_profit_pct_to_sell = take_profit_pct_to_sell
        self.stop_loss_type = stop_loss_type
        self.stop_loss_trigger_pct = stop_loss_trigger_pct
        self.stop_loss_hold_intervals = stop_loss_hold_intervals
        self.state_waiting = state_waiting
        self.state_entering_position = state_entering_position
        self.state_taking_profit = state_taking_profit
        self.state_stopping_loss = state_stopping_loss
        self.state_terminated = state_terminated


# TODO iterate through library, generate and return
class PlayFactory:
    """
    Read from weather categories and configs from storage
    Produce a PlayLibray

    """

    def generate_play_items(raw_library: set, categories: set, conditions: set):
        g = globals().copy()
        found = "PlayOrchestrator" in g.keys()
        for this_name, obj in g.items():
            if this_name == "PlayOrchestrator":
                print("banana")

    ...


class PlayLibrary:
    categories: set[str]
    store: IParameterStore
    _store_path: str
    _raw_library: str
    library: set[set[PlayItem]]
    _conditions: list[str] = ["bull", "sideways", "choppy", "bear"]
    categories: set[str]

    def __init__(
        self,
        store: IParameterStore,
        store_path: str = "/tabot/play_library/paper/play_index",
    ):
        self.store = store
        self._store_path = store_path
        self._raw_library = self._get_library()
        self.library = PlayFactory.generate_play_items(
            raw_library=self._raw_library,
            categories=self.categories,
            conditions=self._conditions,
        )

    def _get_library(self):
        categories = set(json.loads(self.store.get(self._store_path)))


z = PlayLibrary(store=Ssm())
z._get_library()


class WeatherResult:
    """
    SymbolCategory
        Name                        crypto_alt
        Symbols                     {ADA, AVAX}
        Condition                   bull
    SymbolCategory
        Name                        crypto_stable
        Symbols                     {BTC, ETH}
        Condition                   choppy
    """

    class WeatherItem:
        symbols: set[str]
        condition: str

        def __init__(self, symbols, condition) -> None:
            self.symbols = symbols
            self.condition = condition

        def __repr__(self) -> str:
            return f"WeatherItem {str(self.symbols)}"

    def get_all(self):
        ...

    def get_one(self, key: str):
        ...


class StubWeatherResult(WeatherResult):
    _mock_weather: dict[str, WeatherResult.WeatherItem]

    def __init__(self) -> None:
        self._mock_weather = dict()
        self._mock_weather["crypto_alt"] = self.WeatherItem(
            symbols={"ADA, AVAX"}, condition="bull"
        )
        self._mock_weather["crypto_stable"] = self.WeatherItem(
            symbols={"BTC, ETH"}, condition="choppy"
        )

    def get_all(self):
        return self._mock_weather

    def get_one(self, key: str):
        return self._mock_weather[key]


class IWeatherReader(ABC):
    @abstractmethod
    def __init__(self):
        ...

    @abstractmethod
    def get_all(self) -> set[WeatherResult]:
        ...

    @abstractmethod
    def get_one(self, category: str) -> WeatherResult:
        ...


class StubWeather(IWeatherReader):
    _tm: TimeManager

    def __init__(self, tm: TimeManager):
        self._tm = tm

    def get_all(self) -> set[WeatherResult]:
        return StubWeatherResult().get_all()

    def get_one(self, category: str) -> WeatherResult:
        return StubWeatherResult().get_one(category)


class PlayOrchestrator:
    """
    Startup responsibilities:
        Instantiates TimeManager
        Read config from store
        Hand it to PlayFactory to mux symbols, bid sizes, state objects to use, state config parameters
        Gets back an object called PlayLibrary with everything instantiated
        Instantiates SymbolHandler
        Instantiates Weather
        Instantiates a PlayHandler based on weather x PlayLibrary

    Run responsibilities:
        TimeManger tick
        Checks weather - has it changed?
        If weather has changed:
            Tell PlayHandler to shut down
        Else:
            Tell PlayHandler to run

    Shutdown responsibilities:
        Tell PlayHandler to shut down


    """

    time_manager: TimeManager
    symbols: set[Symbol]

    def __init__(self) -> None:
        self.time_manager = TimeManager()

    ...
