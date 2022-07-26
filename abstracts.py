from abc import ABC, abstractmethod
from symbol import Symbol
import uuid
import logging

log = logging.getLogger(__name__)

"""
At a minimum, a Strategy must implement the following interfaces:
    IStateWaiting
    IStateEnteringPosition
    IStateStoppingLoss
    IStateTakingProfit
    IStateTerminated

A Strategy may also choose the extend the following abstracts:
    APlayController

It is possible but unusual for a Strategy to extend the following abstracts (usually if you want to add a new state/remove a state):
    APlayConfig
    APlayTemplate
    APlayInstance
    AInstanceTelemetry
    APlayTelemetry
    AState
"""

STATE_STAY = 0
STATE_SPLIT = 1
STATE_CHANGE = 2


class AState(ABC):
    @abstractmethod
    def __init__(self, previous_state) -> None:
        log.debug(f"Started {self.__repr__()}")
        self.previous_state = previous_state

    @abstractmethod
    def check_exit(self):
        ...

    @abstractmethod
    def do_exit(self):
        ...

    def __del__(self):
        log.log(9, f"Deleting {self.__repr__()}")

    def __repr__(self) -> str:
        return self.__class__.__name__


class IStateWaiting(AState):
    @abstractmethod
    def __init__(self, previous_state: AState = None) -> None:
        super().__init__(previous_state=previous_state)


class IStateEnteringPosition(AState):
    @abstractmethod
    def __init__(self, previous_state: AState) -> None:
        super().__init__(previous_state=previous_state)


class IStateTakingProfit(AState):
    @abstractmethod
    def __init__(self, previous_state: AState) -> None:
        super().__init__(previous_state=previous_state)


class IStateStoppingLoss(AState):
    @abstractmethod
    def __init__(self, previous_state: AState) -> None:
        super().__init__(previous_state=previous_state)


class IStateTerminated(AState):
    @abstractmethod
    def __init__(self, previous_state: AState) -> None:
        super().__init__(previous_state=previous_state)


class AInstanceTelemetry(ABC):
    def __init__(self, play_telemetry) -> None:
        self.bought_total_value = 0
        self.bought_unit_count = 0
        self.sold_total_value = 0
        self.sold_unit_count = 0
        self.play_telemetry = play_telemetry


class APlayTelemetry(ABC):
    def __init__(self) -> None:
        self.original_unit_stop_loss = 0
        self.original_unit_target_price = 0
        self.bought_total_value = 0
        self.bought_unit_count = 0
        self.sold_total_value = 0
        self.sold_unit_count = 0
        self.instance_count = 0


class APlayTemplate(ABC):
    def __init__(
        self,
        buy_signal_strength: float,
        take_profit_trigger_pct_of_risk: float,
        take_profit_pct_to_sell: float,
        stop_loss_trigger_pct: float,
        stop_loss_type: str = "market",
        stop_loss_hold_intervals: int = 1,
        buy_timeout_intervals: int = 2,
    ) -> None:
        self.buy_signal_strength = buy_signal_strength
        self.take_profit_trigger_pct_of_risk = take_profit_trigger_pct_of_risk
        self.take_profit_pct_to_sell = take_profit_pct_to_sell
        self.stop_loss_trigger_pct = stop_loss_trigger_pct
        self.stop_loss_type = stop_loss_type
        self.stop_loss_hold_intervals = stop_loss_hold_intervals
        self.buy_timeout_intervals = buy_timeout_intervals


class APlayConfig(ABC):
    state_waiting: AState = None
    state_entering_position: AState = None
    state_taking_profit: AState = None
    state_stopping_loss: AState = None
    state_terminated: AState = None
    buy_budget: float = None
    play_templates: list = None

    def __init__(
        self,
        state_waiting: AState,
        state_entering_position: AState,
        state_taking_profit: AState,
        state_stopping_loss: AState,
        state_terminated: AState,
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


class APlayInstance(ABC):
    def __init__(
        self, template: APlayTemplate, play_controller, state=None, state_args=None
    ) -> None:
        self.config = template
        self.parent = play_controller
        self.telemetry = AInstanceTelemetry(play_telemetry=play_controller.telemetry)

        if state == None:
            self._state = play_controller.play_config.state_waiting()
        else:
            self._state = state(**state_args)

    def run(self):
        exit_met, new_state = self._state.check_exit()
        if not exit_met:
            log.log(9, "no change")
            return

        self.state = new_state

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, new_state):
        if not isinstance(new_state, type):
            _msg = f"Specified state '{new_state}' must be a class"
            log.error(_msg)
            raise RuntimeError(_msg)

        self._state.do_exit()
        log.info(f"do_exit() successful on {self._state}")

        self._state = new_state(previous_state=self._state)
        log.info(f"successfully set new state to {self._state}")


class APlayController(ABC):
    def __init__(
        self,
        symbol: Symbol,
        play_config: APlayConfig,
        play_instance_class: APlayInstance = APlayInstance,
    ) -> None:
        self.symbol = symbol
        self.play_config = play_config
        self.play_id = self._generate_play_id()
        # PlayInstance class to be use
        self.play_instance_class = play_instance_class
        self.instances = []
        self.telemetry = APlayTelemetry()

    def start_play(self):
        if len(self.instances) > 0:
            raise RuntimeError("Already started plays, can't call start_play() twice")

        for template in self.play_config.play_templates:
            self.instances.append(self.play_instance_class(template, self))

        self.run()

    def register_instance(self, new_instance):
        self.instances.append(new_instance)

    def _generate_play_id(self, length: int = 6):
        return "play-" + self.symbol.yf_symbol + uuid.uuid4().hex[:length].upper()

    def run(self):
        for i in self.instances:
            i.run()


# TODO
# be able to do a split
# instance play changes implementations
# hook up play and instance telemetry callbacks

# if there is a split, what happens?
# during buy:
# start a new instance at partial fill
# original instance continues on until its totally full
# new instance is instantiated using fill information from broker api, gets a new sub-identifier and gets a new telemetry object
# new instance continues on
