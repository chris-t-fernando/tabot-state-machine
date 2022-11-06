from parameter_store import IParameterStore
from .play_config import PlayConfig
from core import StrategyHandler
import json


class PlayLibrary:
    store: IParameterStore
    _store_path: str
    symbol_categories: dict[str, set[str]]
    market_conditions: set[str]
    unique_symbols: set[str]
    library: set[set[PlayConfig]]
    strategy_handler: StrategyHandler

    def __init__(
        self,
        store: IParameterStore,
        strategy_handler: StrategyHandler,
        store_path: str = "/tabot/play_library/paper",
    ):
        self.store = store
        self.strategy_handler = strategy_handler
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

    # TODO find a way to access strategy config objects where they're loaded
    def _resolve_play_config_object(self, play_config_str: str = None):

        if play_config_str:
            if play_config_str in self.strategy_handler:
                return self.strategy_handler[play_config_str]
            else:
                raise RuntimeError(
                    f"Unable to find PlayConfig object '{play_config_str}' in globals(). Did you import it?"
                )

        else:
            return PlayConfig

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
                    if "config_object" in config:
                        # a custom config object was specified
                        config_str = config["config_object"]
                    else:
                        config_str = None

                    config_object = self._resolve_play_config_object(
                        play_config_str=config_str
                    )

                    play_configs.append(
                        config_object(
                            symbol_category=cat,
                            market_condition=condition,
                            strategy_handler=self.strategy_handler,
                            **config,
                        )
                    )

                library[cat][condition] = play_configs

        return library
