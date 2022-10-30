"""from .instance_state import State


class IPlayConfig:
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
        ...

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
        ...

    def _state_str_to_object(self, state_str):
        ...
"""
