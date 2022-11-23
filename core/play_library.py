from parameter_store import IParameterStore
from .play_config import PlayConfig, JSONEncoder as PCJsonEncoder
from core import StrategyHandler
import json


class PlayLibrary:
    store: IParameterStore
    _store_path: str
    algos: set
    symbol_categories: dict[str, set[str]]
    market_conditions: set[str]
    unique_symbols: set[str]
    library: dict[str, dict[str, PlayConfig]]
    strategy_handler: StrategyHandler

    def __init__(
        self,
        store: IParameterStore,
        strategy_handler: StrategyHandler,
        store_path: str = "/tabot/play_library/paper",
    ):
        self.algos = set()
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
    def _resolve_str_to_object(self, object_string: str = None):

        if object_string:
            # TODO in strategy_handler is too ambiguous - should be strategy_handler.objects or something
            if object_string in self.strategy_handler:
                return self.strategy_handler[object_string]
            else:
                raise RuntimeError(
                    f"Unable to find class '{object_string}' in globals(). Did you import it?"
                )

        else:
            return PlayConfig

    # TODO instantiate symbols, lifecycle them somehow
    def _setup_library(self) -> dict:
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

                    config_object = self._resolve_str_to_object(
                        object_string=config_str
                    )

                    for a in config["algos"]:
                        # hold on to each algo
                        algo_obj = self._resolve_str_to_object(object_string=a)
                        self.algos.add(algo_obj)

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

    def json_encode(self):
        return JSONEncoder().encode(self.library)

    # this is horrific
    def library_as_dict(self):
        return_dict = dict()
        for v in self.library.values():
            for lv in v.values():
                for pcv in lv:
                    for pcv_key in dir(pcv):
                        try:
                            getattr(getattr(pcv, pcv_key), "_cls_str")
                            is_state = True
                        except:
                            is_state = False

        return self.library.as_dict()


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, PlayConfig):
            return PCJsonEncoder().encode(obj)

        return json.JSONEncoder.default(self, obj)
