from broker_api import AlpacaAPI, BackTestAPI, ITradeAPI
from abc import ABC, abstractmethod
from core import TimeManager
from parameter_store import Ssm, IParameterStore
from core import TimeManager, State, SymbolPlay, ControllerConfig
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

import symbol

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
    name: str
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
        return (
            f"PlayConfig '{self.name}' {self.symbol_category} {self.market_condition}"
        )

    def __init__(
        self,
        symbol_category: str,
        market_condition: str,
        name: str,
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
        self.name = name
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
    symbol_categories: dict[str, set[str]]
    market_conditions: set[str]
    unique_symbols: set[str]
    library: set[set[PlayConfig]]

    def __init__(
        self,
        store: IParameterStore,
        store_path: str = "/tabot/play_library/paper",
    ):
        self.store = store
        self._store_path = store_path
        category_set = self._get_categories()

        self.symbol_categories = self._enumerate_symbols(symbol_categories=category_set)
        self.market_conditions = self._get_market_conditions()
        self.unique_symbols = self._unique_symbols(self.symbol_categories)

        self.library = self._setup_library()

    def _get_categories(self) -> set:
        path = f"{self._store_path}/symbol_categories"
        return set(json.loads(self.store.get(path)))

    def _get_market_conditions(self) -> set:
        path = f"{self._store_path}/market_conditions"
        return set(json.loads(self.store.get(path)))

    def _enumerate_symbols(self, symbol_categories: set[str]) -> dict[str, set[str]]:
        cat_sym_map = dict()
        for cat in symbol_categories:
            cat_sym_map[cat] = set(
                json.loads(self.store.get(f"{self._store_path}/{cat}/symbols"))
            )
        return cat_sym_map

    def _unique_symbols(self, symbol_categories: dict[str, set[str]]):
        unique_symbols = set()
        for cat, symbols in symbol_categories.items():
            unique_symbols |= symbols

        return unique_symbols

    # TODO instantiate symbols, lifecycle them somehow
    def _setup_library(self):
        # /root/symbol_categories - the different symbol groups eg crypto_stable
        # /root/market_conditions - the different market conditions eg choppy
        # /root/crypto_stable/bear - example path where play configs get read out
        library = dict()
        for cat in self.symbol_categories:
            library[cat] = dict()
            for condition in self.market_conditions:
                # grab the raw json config from store
                config_json = json.loads(
                    self.store.get(f"{self._store_path}/{cat}/{condition}")
                )

                # store will return a list of plays, need to instantiate each into a PlayConfig object
                play_configs = list()
                for config in config_json:
                    # TODO PlayConfig is the same thing as core.InstanceTemplate and macd.MacdInstanceTemplate
                    # clean it up
                    # make playconfig object configurable via object lookup
                    # make a playconfig object for macd that supports the additional fields (buy_signal_strength etc)
                    play_configs.append(PlayConfig(cat, condition, **config))

                library[cat][condition] = play_configs

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

    def get_all(self) -> dict[str, WeatherResult]:
        return self._mock_weather

    def get_one(self, category: str) -> WeatherResult:
        return self._mock_weather[category]


class IWeatherReader(ABC):
    @abstractmethod
    def __init__(self):
        ...

    @abstractmethod
    def get_all(self) -> dict[str, WeatherResult]:
        ...

    @abstractmethod
    def get_one(self, category: str) -> WeatherResult:
        ...


class StubWeather(IWeatherReader):
    _tm: TimeManager

    def __init__(self, tm: TimeManager):
        self._tm = tm

    def get_all(self) -> dict[str, WeatherResult]:
        return StubWeatherResult().get_all()

    def get_one(self, category: str) -> WeatherResult:
        return StubWeatherResult().get_one(category)


class SymbolHandler:
    """Handles SymbolPlay objects"""

    _symbols: dict[Symbol]
    _ta_algos: set
    time_manager: TimeManager
    started: bool
    _play_controllers: set[SymbolPlay]
    active_play_controllers: set[SymbolPlay]
    play_config: PlayConfig
    broker: ITradeAPI

    def __init__(
        self,
        symbols: set[Symbol],
        time_manager: TimeManager,
        play_config: PlayConfig,
        broker: ITradeAPI,
    ) -> None:
        self._symbols = symbols
        self._ta_algos = set()
        self.started = False
        self._play_controllers = set()
        self.time_manager = time_manager
        self.play_config = play_config
        self.broker = broker

    def __repr__(self) -> str:
        return f"SymbolGroup {self.play_config.name} ({len(self._symbols)} symbols)"

    @property
    def active_play_controllers(self) -> set[SymbolPlay]:
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
                f"Failed to start SymbolGroup {self.name} - must add symbols to the group first"
            )

        for s, s_obj in self._symbols.items():
            _new_controller = SymbolPlay(s_obj, self.play_config, self.broker)
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
        return self.time_manager.now


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
    time_manager: TimeManager

    def __init__(
        self,
        symbols: set[Symbol],
        play_configs: list[PlayConfig],
        broker: ITradeAPI,
        time_manager: TimeManager,
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
    symbol_data: SymbolData
    weather: IWeatherReader
    _active_category_handlers: dict[str, CategoryHandler]
    _inactive_category_handlers: set

    def __init__(self, store: IParameterStore) -> None:
        self._active_category_handlers = dict()
        self._inactive_category_handlers = set()
        self.store = store
        self.time_manager = TimeManager()
        self.broker = BackTestAPI(time_manager=self.time_manager)
        self.play_library = PlayLibrary(store)
        self.symbol_data = SymbolData(self.play_library.unique_symbols)
        self.weather = StubWeather(self.time_manager)

    def start(self):
        weather = self.weather.get_all()
        for cat in self.play_library.symbol_categories:
            cat_symbols_obj = dict()
            w = weather[cat].condition
            plays = self.play_library.library[cat][w]
            cat_symbols_str = self.play_library.symbol_categories[cat]

            # TODO this has no business being here - it should be part of PlayLibrary
            for s in cat_symbols_str:
                cat_symbols_obj[s] = self.symbol_data.symbols[s]

            c = CategoryHandler(
                symbols=cat_symbols_obj,
                play_configs=plays,
                broker=self.broker,
                time_manager=self.time_manager,
            )
            c.start()

            pc = SymbolHandler(
                "vanana",
                symbols=self.symbol_data.symbols,
                time_manager=self.time_manager,
                play_config=plays,
                broker=self.broker,
            )
            pc.start()

            print("banana")

    def get_active_handler(self, category: str) -> SymbolPlay:
        if category not in self.play_library.library:
            raise RuntimeError(f"Cannot find symbol category named '{category}'")

        if category not in self._active_category_handlers:
            return False

        return self._active_category_handlers[category]

    def start_handler(self, category: str, condition: str) -> SymbolPlay:
        # make sure the symbol category exists
        if category not in self.play_library.library:
            raise RuntimeError(f"Cannot find symbol category named '{category}'")

        # make sure we aren't already running a play for this symbol category
        if self.get_active_handler(category):
            # already running
            raise RuntimeError(
                f"Already running a PlayController for symbol category '{category}'"
            )

        # make sure the market condition exists
        if condition not in self.play_library.market_conditions:
            raise RuntimeError(f"Cannot find market condition named '{condition}'")

        self._active_category_handlers[category] = CategoryHandler(
            symbols=self.play_library.library
        )

    # TODO property for running plays


store = Ssm()
po = PlayOrchestrator(store)
po.start()
