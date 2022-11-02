from abc import ABC
from .state import State


class ControllerConfig(ABC):
    state_waiting: State = None
    state_entering_position: State = None
    state_taking_profit: State = None
    state_stopping_loss: State = None
    state_terminated: State = None
    buy_budget: float = None
    play_templates: list = None

    def __init__(
        self,
        state_waiting: State,
        state_entering_position: State,
        state_taking_profit: State,
        state_stopping_loss: State,
        state_terminated: State,
        buy_budget: float,
        play_templates: list,
    ) -> None:
        self.state_waiting = state_waiting
        self.state_entering_position = state_entering_position
        self.state_taking_profit = state_taking_profit
        self.state_stopping_loss = state_stopping_loss
        self.state_terminated = state_terminated
        self.buy_budget = buy_budget
        self.play_templates = play_templates
