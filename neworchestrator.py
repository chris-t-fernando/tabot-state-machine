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

import logging

stream_handler = logging.StreamHandler()
formatter = logging.Formatter(
    "%(asctime)s - %(name)16s - %(levelname)8s - %(funcName)15s - %(message)s"
)
stream_handler.setFormatter(formatter)
root_logger = logging.getLogger()
root_logger.setLevel(logging.CRITICAL)
root_logger.addHandler(stream_handler)

level = 9
log = logging.getLogger(__name__)
log.setLevel(level)
logging.getLogger("core.abstracts").setLevel(level)
logging.getLogger("strategies.macd").setLevel(level)


class PlayConfig:
    symbol_category: str
    market_condition: str
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

    def __repr__(self) -> str:
        return f"{self.symbol_category} {self.market_condition}"

    def __init__(
        self,
        symbol_category: str,
        market_condition: str,
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
        self.symbol_category = symbol_category
        self.market_condition = market_condition
        self.max_play_size = max_play_size
        self.buy_timeout_intervals = buy_timeout_intervals
        self.buy_order_type = buy_order_type
        self.take_profit_risk_multiplier = take_profit_risk_multiplier
        self.take_profit_pct_to_sell = take_profit_pct_to_sell
        self.stop_loss_type = stop_loss_type
        self.stop_loss_trigger_pct = stop_loss_trigger_pct
        self.stop_loss_hold_intervals = stop_loss_hold_intervals
        self.state_waiting = self._state_str_to_object(state_waiting)
        self.state_entering_position = self._state_str_to_object(
            state_entering_position
        )
        self.state_taking_profit = self._state_str_to_object(state_taking_profit)
        self.state_stopping_loss = self._state_str_to_object(state_stopping_loss)
        self.state_terminated = self._state_str_to_object(state_terminated)

    def _state_str_to_object(self, state_str):
        g = globals().copy()
        if state_str in g.keys():
            return g[state_str]

        raise RuntimeError(
            f"Could not find {state_str} in globals() - did you import it?"
        )


class PlayLibrary:
    symbol_categories: set[str]
    store: IParameterStore
    _store_path: str
    _raw_library: str
    _uninstantiated_symbols: set[Symbol]
    library: set[set[PlayConfig]]

    def __init__(
        self,
        store: IParameterStore,
        store_path: str = "/tabot/play_library/paper",
    ):
        self.uninstantiated_symbols = set()
        self.store = store
        self._store_path = store_path
        self._raw_library = self._get_library()

    # TODO some of this goes straight in to state, some gets returned. why?
    # TODO instantiate symbols, lifecycle them somehow
    def _get_library(self):
        # /root/symbol_categories - the different symbol groups eg crypto_stable
        # /root/market_conditions - the different market conditions eg choppy
        # /root/crypto_stable/bear - example path where play configs get read out
        self.symbol_categories = set(
            json.loads(self.store.get(f"{self._store_path}/symbol_categories"))
        )
        self.market_conditions = set(
            json.loads(self.store.get(f"{self._store_path}/market_conditions"))
        )

        library = dict()
        for cat in self.symbol_categories:
            library[cat] = dict()
            new_symbols = set(
                json.loads(self.store.get(f"{self._store_path}/{cat}/symbols"))
            )
            if len(new_symbols & self.uninstantiated_symbols) > 0:
                log.warning(
                    f"Symbol appears in more than one category: {new_symbols&self.uninstantiated_symbols}"
                )
            self.uninstantiated_symbols |= new_symbols

            for condition in self.market_conditions:
                config_json = json.loads(
                    self.store.get(f"{self._store_path}/{cat}/{condition}")
                )
                library[cat][condition] = PlayConfig(cat, condition, **config_json)
        return library


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
