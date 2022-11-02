from .state import State

from abc import abstractmethod


class StateWaiting(State):
    _cls_str = "IStateWaiting"

    @abstractmethod
    def __init__(self, previous_state: State, parent_instance=None) -> None:
        super().__init__(parent_instance=parent_instance, previous_state=previous_state)
