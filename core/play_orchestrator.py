from parameter_store import IParameterStore
from broker_api import BackTestAPI
from symbol import Symbol
import pandas as pd
import uuid
from datetime import datetime

from .time_manager import BackTestTimeManager, ITimeManager
from .play_library import PlayLibrary
from .symbol_data import SymbolData
from .weather import IWeatherReader, StubWeather, WeatherResult
from .category_handler import CategoryHandler
from .symbol_play import SymbolPlay
from .strategy_handler import StrategyHandler
from .constants import RT_BACKTEST, RT_PAPER, RT_REAL, RT_DICT
from .telemetry import ITelemetry, Sqs

import logging

log = logging.getLogger(__name__)


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
    time_manager: ITimeManager
    play_library: PlayLibrary
    symbol_data: SymbolData
    weather: IWeatherReader
    _active_category_handlers: dict[str, CategoryHandler]
    _inactive_category_handlers: set
    run_type: int
    id: str

    def __init__(
        self,
        store: IParameterStore,
        strategy_handler: StrategyHandler,
        run_type: int = RT_BACKTEST,
    ) -> None:
        # init stuff
        self._active_category_handlers = dict()
        self._inactive_category_handlers = set()
        self.id = self._generate_id()
        self.store = store
        self.strategy_handler = strategy_handler
        self.run_type = run_type
        self.telemetry = Sqs(store, run_type)

        # set up play library from store
        self.play_library = PlayLibrary(store=store, strategy_handler=strategy_handler)

        # set up time manager
        tm = self._get_time_manager(run_type)
        self.time_manager: ITimeManager = tm()

        # set up symbol data
        self.symbol_data = SymbolData(
            self.play_library.unique_symbols, self.play_library.algos, self.time_manager
        )

        # register symbols into time manager, so it knows the horizon
        self.time_manager.add_symbols(self.symbol_data.unique_symbols)

        # set up API
        self.broker = BackTestAPI(
            time_manager=self.time_manager,
            symbol_objects=self.symbol_data.unique_symbols,
        )

        # set up weather
        self.weather = StubWeather(self.time_manager)
        self._last_weather = self.weather.get_all()

        self.telemetry.emit(
            event="Play start",
            play_id=str(self),
            run_type=RT_DICT[run_type],
            start_time_utc=str(datetime.utcnow()),
            start_time_local=str(datetime.astimezone(datetime.now())),
            play_library_symbol_categories={
                key: list(val)
                for (key, val) in self.play_library.symbol_categories.items()
            },
            play_library_conditions=list(self.play_library.market_conditions),
            # play_library=self.play_library.json_encode(),
        )

    def _generate_id(self, length: int = 6):
        return uuid.uuid4().hex[:length].upper()

    def _get_time_manager(self, run_type) -> ITimeManager:
        if run_type == RT_BACKTEST:
            return BackTestTimeManager
        else:
            # TODO!!!
            return

    def start(self):
        self.time_manager.start()
        self._last_weather = self.weather.get_all()
        for cat in self.play_library.symbol_categories:
            w = self._last_weather[cat].condition
            self.start_handler(cat, w)

    def _get_plays(self, category, weather):
        return self.play_library.library[category][weather]

    def _get_symbol_obj(self, cat: str) -> dict[str, Symbol]:
        cat_symbols_str = self.play_library.symbol_categories[cat]

        cat_symbols_obj = dict()
        # TODO this has no business being here - it should be part of PlayLibrary
        for s in cat_symbols_str:
            cat_symbols_obj[s] = self.symbol_data.symbols[s]
        return cat_symbols_obj

    """
    Run responsibilities:
        TimeManger tick
        Checks weather - has it changed?
        If weather has changed:
            Tell PlayHandler to shut down
        Else:
            Tell PlayHandler to run
    """

    def run(self):
        self.time_manager.tick()
        new_weather = self.weather.get_all()

        for cat in self.play_library.symbol_categories:
            last_w = self._last_weather[cat].condition
            new_w = new_weather[cat].condition
            if last_w != new_w:
                # weather has changed
                log.info(f"Weather for {cat} has changed (was: {last_w}, now: {new_w})")
                self.stop_handler(category=cat)
                this_handler = self.start_handler(category=cat, condition=new_w)

            else:
                # weather has not changed
                this_handler = self.get_active_handler(category=cat)

            this_handler.run()

        self._last_weather = new_weather

    def get_active_handler(self, category: str) -> CategoryHandler:
        if category not in self.play_library.library:
            raise InvalidCategory(
                f"Cannot find symbol category named '{category}' - check config"
            )

        if category not in self._active_category_handlers:
            raise NoRunningHandlerForCategory(f"No running handler for {category}")

        return self._active_category_handlers[category]

    def start_handler(self, category: str, condition: str) -> CategoryHandler:
        # make sure the symbol category exists
        if category not in self.play_library.library:
            raise InvalidCategory(
                f"Cannot find symbol category named '{category}' - check config"
            )

        # make sure we aren't already running a play for this symbol category
        try:
            self.get_active_handler(category)
            raise HandlerForCategoryAlreadyRunning(
                f"A handler is already running for {category}. Stop it before starting a new one"
            )
            # already running
        except NoRunningHandlerForCategory:
            # expected exception - its good if this fires, means there wasn't a handler running for this
            ...
        except:
            raise

        # make sure the market condition exists
        if condition not in self.play_library.market_conditions:
            raise InvalidMarketCondition(
                f"Cannot find market condition named '{condition}'"
            )

        cat_symbols_obj = self._get_symbol_obj(category)
        plays = self._get_plays(category, condition)

        new_handler = CategoryHandler(
            symbols=cat_symbols_obj,
            play_configs=plays,
            broker=self.broker,
            time_manager=self.time_manager,
            run_id=self.__str__(),
            telemetry=self.telemetry,
        )
        new_handler.start()
        self._active_category_handlers[category] = new_handler
        return new_handler

    def stop_handler(self, category: str) -> bool:
        # make sure the symbol category exists
        if category not in self.play_library.library:
            raise InvalidCategory(
                f"Cannot find symbol category named '{category}' - check config"
            )

        # make sure we aren't already running a play for this symbol category
        try:
            handler = self.get_active_handler(category)
            # TODO wrap this in a try...except
            handler.stop()
            self._inactive_category_handlers.add(handler)
            del self._active_category_handlers[category]

            return True

        except Exception as e:
            raise

    # TODO property for running plays
    @property
    def first_record(self) -> pd.Timestamp:
        return self.time_manager.first

    @property
    def last_record(self) -> pd.Timestamp:
        return self.time_manager.last

    @property
    def now(self) -> pd.Timestamp:
        return self.time_manager.now

    @property
    def tick_ttl(self) -> int:
        return self.time_manager.tick_ttl

    @property
    def eof(self) -> bool:
        if self.now == self.last_record:
            return True
        return False

    def sleep(self) -> None:
        if self.run_type == RT_BACKTEST:
            return
        else:
            # TODO
            ...

    def __str__(self) -> str:
        return f"{self.__class__.__name__}-{self.id}"


class InvalidCategory(Exception):
    ...


class NoRunningHandlerForCategory(Exception):
    ...


class HandlerForCategoryAlreadyRunning(Exception):
    ...


class InvalidMarketCondition(Exception):
    ...
