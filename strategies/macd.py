from core.abstracts import (
    IStateWaiting,
    IStateEnteringPosition,
    State,
    IStateStoppingLoss,
    IStateTakingProfit,
    IStateTerminated,
    STATE_STAY,
    STATE_SPLIT,
    STATE_MOVE,
)
import logging

log = logging.getLogger(__name__)


class MacdStateWaiting(IStateWaiting):
    def __init__(self, previous_state: State = None) -> None:
        super().__init__(previous_state=previous_state)
        log.log(9, f"Finished initialising {self}")

    def check_exit(self):
        log.log(9, f"checking exit on {self}")
        return STATE_MOVE, MacdStateEnteringPosition, {}

    def do_exit(self):
        log.log(9, f"doing exit on {self}")
        return


class MacdStateEnteringPosition(IStateEnteringPosition):
    def __init__(self, previous_state: State) -> None:
        super().__init__(previous_state=previous_state)

    def check_exit(self):
        log.log(9, f"checking exit on {self}")
        return STATE_MOVE, MacdStateTakingProfit, {}

    def do_exit(self):
        log.log(9, f"doing exit on {self}")
        return


class MacdStateTakingProfit(IStateTakingProfit):
    def __init__(self, previous_state: State) -> None:
        super().__init__(previous_state=previous_state)

    def check_exit(self):
        log.log(9, f"checking exit on {self}")
        return STATE_MOVE, MacdStateStoppingLoss, {}

    def do_exit(self):
        log.log(9, f"doing exit on {self}")
        return


class MacdStateStoppingLoss(IStateStoppingLoss):
    def __init__(self, previous_state: State) -> None:
        super().__init__(previous_state=previous_state)

    def check_exit(self):
        log.log(9, f"checking exit on {self}")
        return STATE_MOVE, MacdStateWaiting, {}

    def do_exit(self):
        log.log(9, f"doing exit on {self}")
        return


class MacdStateTerminated(IStateTerminated):
    def __init__(self, previous_state: State) -> None:
        super().__init__(previous_state=previous_state)

    def check_exit(self):
        log.log(9, f"checking exit on {self}")
        return STATE_STAY, None, {}

    def do_exit(self):
        raise NotImplementedError(f"Terminated state cannot implement do_exit()")
