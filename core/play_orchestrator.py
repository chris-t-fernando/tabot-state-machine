from parameter_store import IParameterStore
from broker_api import BackTestAPI

from .time_manager import TimeManager
from .play_library import PlayLibrary
from .symbol_data import SymbolData
from .weather import IWeatherReader, StubWeather
from .category_handler import CategoryHandler
from .symbol_handler import SymbolHandler
from .symbol_play import SymbolPlay
from .strategy_handler import StrategyHandler


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

    def __init__(
        self, store: IParameterStore, strategy_handler: StrategyHandler
    ) -> None:
        self._active_category_handlers = dict()
        self._inactive_category_handlers = set()
        self.store = store
        self.strategy_handler = strategy_handler
        self.time_manager = TimeManager()
        self.broker = BackTestAPI(time_manager=self.time_manager)
        self.play_library = PlayLibrary(store=store, strategy_handler=strategy_handler)
        self.symbol_data = SymbolData(
            self.play_library.unique_symbols, self.play_library.algos
        )
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

            # pc = SymbolHandler(
            #    "vanana",
            #    symbols=self.symbol_data.symbols,
            #    time_manager=self.time_manager,
            #    play_config=plays,
            #    broker=self.broker,
            # )
            # pc.start()

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
        ...
