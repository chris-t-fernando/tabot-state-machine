from abstracts import (
    IStateWaiting,
    IStateEnteringPosition,
    AState,
    IStateStoppingLoss,
    IStateTakingProfit,
    IStateTerminated,
    STATE_STAY,
    STATE_SPLIT,
    STATE_CHANGE
)
import logging

log = logging.getLogger(__name__)


class MacdStateWaiting(IStateWaiting):
    def __init__(self, previous_state: AState = None) -> None:
        super().__init__(previous_state=previous_state)
        log.log(9, f"Finished initialising {self}")

    def check_exit(self):
        log.log(9, f"checking exit on {self}")
        return True, MacdStateEnteringPosition

    def do_exit(self):
        log.log(9, f"doing exit on {self}")
        return


class MacdStateEnteringPosition(IStateEnteringPosition):
    def __init__(self, previous_state: AState) -> None:
        super().__init__(previous_state=previous_state)

    def check_exit(self):
        log.log(9, f"checking exit on {self}")
        return True, MacdStateTakingProfit

    def do_exit(self):
        log.log(9, f"doing exit on {self}")
        return


class MacdStateTakingProfit(IStateTakingProfit):
    def __init__(self, previous_state: AState) -> None:
        super().__init__(previous_state=previous_state)

    def check_exit(self):
        log.log(9, f"checking exit on {self}")
        return True, MacdStateStoppingLoss

    def do_exit(self):
        log.log(9, f"doing exit on {self}")
        return


class MacdStateStoppingLoss(IStateStoppingLoss):
    def __init__(self, previous_state: AState) -> None:
        super().__init__(previous_state=previous_state)

    def check_exit(self):
        log.log(9, f"checking exit on {self}")
        return True, MacdStateWaiting

    def do_exit(self):
        log.log(9, f"doing exit on {self}")
        return


class MacdStateTerminated(IStateTerminated):
    def __init__(self, previous_state: AState) -> None:
        super().__init__(previous_state=previous_state)

    def check_exit(self):
        log.log(9, f"checking exit on {self}")
        return False, None

    def do_exit(self):
        raise NotImplementedError(f"Terminated state cannot implement do_exit()")
