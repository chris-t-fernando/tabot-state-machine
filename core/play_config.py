from typing import Any
from core.strategy_handler import StrategyHandler
import json


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
    state_waiting: Any
    state_entering_position: Any
    state_taking_profit: Any
    state_stopping_loss: Any
    state_terminated: Any
    config_object: Any
    strategy_handler: StrategyHandler
    algos: Any

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
        state_waiting,
        state_entering_position,
        state_taking_profit,
        state_stopping_loss,
        state_terminated,
        config_object,
        strategy_handler: StrategyHandler,
        algos,
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
        self.strategy_handler = strategy_handler
        self.state_waiting = self._state_str_to_object(state_waiting)
        self.state_entering_position = self._state_str_to_object(
            state_entering_position
        )
        self.state_taking_profit = self._state_str_to_object(state_taking_profit)
        self.state_stopping_loss = self._state_str_to_object(state_stopping_loss)
        self.state_terminated = self._state_str_to_object(state_terminated)
        self.config_object = self._state_str_to_object(config_object)

    def _state_str_to_object(self, state_str):

        if state_str in self.strategy_handler:
            return self.strategy_handler[state_str]

        raise RuntimeError(
            f"Could not find {state_str} in globals() - did you import it?"
        )


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, "_cls_str"):
            return obj._cls_str

        if hasattr(obj, "strategy_handler"):
            return_dict = obj.__dict__
            orig_dict = return_dict["strategy_handler"]
            del return_dict["strategy_handler"]
            return_dict["strategy_handler"] = []
            for strat_item in orig_dict:
                return_dict["strategy_handler"].append(str(strat_item))
            del return_dict["state_waiting"]
            del return_dict["state_entering_position"]
            del return_dict["state_taking_profit"]
            del return_dict["state_stopping_loss"]
            del return_dict["state_terminated"]
            del return_dict["config_object"]

            return return_dict

        if obj.__module__ == "strategies.macd":
            return f"{obj.__module__}.{obj.__name__}"

        if obj.__module__ == "strategies.macd_play_config":
            return f"{obj.__module__}.{obj.__name__}"

        raise RuntimeError("This should not happen")

        try:

            getattr(obj, "__dict__")
        except AttributeError:
            return json.JSONEncoder.default(self, obj)
        else:
            return_dict = obj.__dict__
            try:
                orig_dict = return_dict["strategy_handler"]
            except KeyError:
                return return_dict
            else:
                # hickety hackity
                del return_dict["strategy_handler"]
                return_dict["strategy_handler"] = []
                for strat_item in orig_dict:
                    return_dict["strategy_handler"].append(str(strat_item))
                return return_dict
