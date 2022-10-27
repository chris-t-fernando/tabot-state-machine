from broker_api import AlpacaAPI, BackTestAPI, ITradeAPI
from abc import ABC, abstractmethod
from core import TimeManager
from parameter_store import Ssm, IParameterStore
from core import TimeManager, State, PlayController, ControllerConfig
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
        return f"PlayConfig {self.symbol_category} {self.market_condition}"

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


class SymbolHandler:
    symbols: set[Symbol]

    def __init__(self, symbols: set[str]):
        self.symbols = set()
        for s in symbols:
            s_obj = self._instantiate_symbol(s)
            self.symbols.add(s_obj)

    def _instantiate_symbol(self, symbol: str) -> bool:
        if symbol in self.symbols:
            log.warning(
                f"Attempted to add symbol {symbol} but it was already instantiated."
            )
            return

        s = Symbol(yf_symbol=symbol)

        return s


#    def _enumerate_symbols(self):
#        for cat in self.symbol_categories:
#            new_symbols = set(
#                json.loads(self.store.get(f"{self._store_path}/{cat}/symbols"))
#            )
#            if len(new_symbols & self.uninstantiated_symbols) > 0:
#                log.warning(
#                    f"Symbol appears in more than one category: {new_symbols&self.uninstantiated_symbols}"
#                )
#            self.uninstantiated_symbols |= new_symbols


class PlayLibrary:
    store: IParameterStore
    _store_path: str
    symbol_categories: set[str]
    market_conditions: set[str]
    symbols: set[str]
    library: set[set[PlayConfig]]

    def __init__(
        self,
        store: IParameterStore,
        store_path: str = "/tabot/play_library/paper",
    ):
        self.store = store
        self._store_path = store_path
        self.symbol_categories = self._get_categories()
        self.market_conditions = self._get_market_conditions()
        self.symbols = self._enumerate_symbols(self.symbol_categories)
        self.library = self._setup_library()

    def _get_categories(self) -> set:
        path = f"{self._store_path}/symbol_categories"
        return set(json.loads(self.store.get(path)))

    def _get_market_conditions(self) -> set:
        path = f"{self._store_path}/market_conditions"
        return set(json.loads(self.store.get(path)))

    def _enumerate_symbols(self, symbol_categories: set[str]) -> set:
        symbols = set()
        for cat in symbol_categories:
            new_symbols = set(
                json.loads(self.store.get(f"{self._store_path}/{cat}/symbols"))
            )
            symbols |= new_symbols

        return symbols

    # TODO instantiate symbols, lifecycle them somehow
    def _setup_library(self):
        # /root/symbol_categories - the different symbol groups eg crypto_stable
        # /root/market_conditions - the different market conditions eg choppy
        # /root/crypto_stable/bear - example path where play configs get read out
        library = dict()
        for cat in self.symbol_categories:
            library[cat] = dict()
            for condition in self.market_conditions:
                config_json = json.loads(
                    self.store.get(f"{self._store_path}/{cat}/{condition}")
                )
                library[cat][condition] = PlayConfig(cat, condition, **config_json)

        return library


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
        * Instantiates TimeManager
        * Read config from store
        * PlayLibrary object with rules instantiated
        * Instantiates SymbolHandler
        * Instantiates Weather

    Start responsibilities
        * Instantiates a PlayHandler based on weather x PlayLibrary

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

    store: IParameterStore
    time_manager: TimeManager
    play_library: PlayLibrary
    symbol_handler: SymbolHandler
    weather: IWeatherReader
    _active_play_controllers: dict[str, PlayConfig]
    _inactive_play_controllers: set

    def __init__(self, store: IParameterStore) -> None:
        self._active_play_controllers = dict()
        self._inactive_play_controllers = set()
        self.store = store
        self.time_manager = TimeManager()
        self.broker = BackTestAPI(time_manager=self.time_manager)
        self.play_library = PlayLibrary(store)
        self.symbol_handler = SymbolHandler(self.play_library.symbols)
        self.weather = StubWeather(self.time_manager)

    def start(self):
        weather = self.weather.get_all()
        for cat in self.play_library.symbol_categories:
            w = weather[cat]
            play = self.play_library.library[cat][w.condition]
            pc = PlayCategory(
                "vanana",
                symbols=self.symbol_handler.symbols,
                time_manager=self.time_manager,
                play_config=play,
                broker=self.broker,
            )
            pc.start()

            print("banana")

    def get_active_controller(self, category: str) -> PlayController:
        if category not in self.play_library.library:
            raise RuntimeError(f"Cannot find symbol category named '{category}'")

        if category not in self._active_play_controllers:
            return False

        return self._active_play_controllers[category]

    def start_controller(self, category: str, condition: str) -> PlayController:
        # make sure the symbol category exists
        if category not in self.play_library.library:
            raise RuntimeError(f"Cannot find symbol category named '{category}'")

        # make sure we aren't already running a play for this symbol category
        if self.get_active_controller(category):
            # already running
            raise RuntimeError(
                f"Already running a PlayController for symbol category '{category}'"
            )

        # make sure the market condition exists
        if condition not in self.play_library.market_conditions:
            raise RuntimeError(f"Cannot find market condition named '{condition}'")

        self._active_play_controllers[category] = PlayController()

    # TODO property for running plays


class PlayCategory:
    _symbols: Set[Symbol]
    _ta_algos: set
    _tm: TimeManager
    started: bool
    name: str
    _play_controllers: Set[PlayController]
    active_play_controllers: Set[PlayController]
    play_config: PlayConfig
    broker: ITradeAPI

    def __init__(
        self,
        name: str,
        symbols: set[Symbol],
        time_manager: TimeManager,
        play_config: ControllerConfig,
        broker: ITradeAPI,
    ) -> None:
        self._symbols = symbols
        self._ta_algos = set()
        self.started = False
        self._play_controllers = set()
        self.name = name
        self._tm = time_manager
        self.play_config = play_config
        self.broker = broker

    def __repr__(self) -> str:
        return f"SymbolGroup {self.name} ({len(self._symbols)} symbols)"

    @property
    def active_play_controllers(self) -> set[PlayController]:
        active = set()
        for c in self._play_controllers:
            if len(c.instances) > 0:
                active.add(c)

        return active

    def start(self):
        if self.started:
            raise RuntimeError(f"SymbolGroup {self.name} is already started")

        if len(self._symbols) == 0:
            raise RuntimeError(
                f"Failed to SymbolGroup {self.name} - must add symbols to the group first"
            )

        for s in self._symbols:
            _new_controller = PlayController(s, self.play_config, self.broker)
            self._play_controllers.add(_new_controller)
            _new_controller.start_play()

        self.started = True

    def stop(self, hard_stop: bool = False):
        for c in self.active_play_controllers:
            c.stop(hard_stop=hard_stop)
            if len(c.instances) > 0:
                log.warning(
                    f"Tried stopping {c} but still {len(c.instances)} instances running (hard_stop={hard_stop})"
                )

    def run(self):
        # need a way to mark retiring play controllers so that they don't get started up again
        log.info(f"Running for period {self.period}")
        for c in self.active_play_controllers:
            c.run()

    @property
    def play_config(self) -> ControllerConfig:
        return self._play_config

    @play_config.setter
    def play_config(self, new_config: ControllerConfig) -> bool:
        if self.started:
            raise RuntimeError(
                f"Can't change play config for {self.name} while play is running"
            )

        self._play_config = new_config

    @property
    def broker(self) -> ITradeAPI:
        return self._broker

    @broker.setter
    def broker(self, new_broker: ITradeAPI):
        if self.started:
            raise RuntimeError(
                f"Can't change broker for {self.name} while play is running"
            )

        self._broker = new_broker

    # use a property here to keep broker and symbol in sync!
    @property
    def period(self):
        return self._tm.now


store = Ssm()
po = PlayOrchestrator(store)
po.start()
