from .state import State
from abc import abstractmethod

import logging

log = logging.getLogger(__name__)


class StateStoppingLoss(State):
    @abstractmethod
    # def __init__(self, parent_instance, previous_state: State) -> None:
    def __init__(self, previous_state: State, parent_instance=None) -> None:
        super().__init__(parent_instance=parent_instance, previous_state=previous_state)

    def check_exit(self):
        super().check_exit()
        terminated_state = self.controller.play_config.state_terminated
        self.log.debug(
            f"{self.parent_instance}: No default clean activities, moving straight to {terminated_state.__name__}"
        )
        return State.STATE_MOVE, terminated_state, {}
