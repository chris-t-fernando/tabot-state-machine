from abc import ABC, abstractmethod
from symbol.symbol import Symbol
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
STATE_MOVE = 2


class State(ABC):
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


class IStateWaiting(State):
    @abstractmethod
    def __init__(self, previous_state: State = None) -> None:
        super().__init__(previous_state=previous_state)


class IStateEnteringPosition(State):
    @abstractmethod
    def __init__(self, previous_state: State) -> None:
        super().__init__(previous_state=previous_state)


class IStateTakingProfit(State):
    @abstractmethod
    def __init__(self, previous_state: State) -> None:
        super().__init__(previous_state=previous_state)


class IStateStoppingLoss(State):
    @abstractmethod
    def __init__(self, previous_state: State) -> None:
        super().__init__(previous_state=previous_state)


class IStateTerminated(State):
    @abstractmethod
    def __init__(self, previous_state: State) -> None:
        super().__init__(previous_state=previous_state)


class InstanceTelemetry(ABC):
    def __init__(self, play_telemetry) -> None:
        self.bought_total_value = 0
        self.bought_unit_count = 0
        self.sold_total_value = 0
        self.sold_unit_count = 0
        self.play_telemetry = play_telemetry


class ControllerTelemetry(ABC):
    def __init__(self) -> None:
        self.original_unit_stop_loss = 0
        self.original_unit_target_price = 0
        self.bought_total_value = 0
        self.bought_unit_count = 0
        self.sold_total_value = 0
        self.sold_unit_count = 0
        self.instance_count = 0


class InstanceTemplate(ABC):
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


class Instance(ABC):
    def __init__(
        self, template: InstanceTemplate, play_controller, state=None, state_args=None
    ) -> None:
        self.config = template
        self.parent_controller = play_controller
        self.telemetry = InstanceTelemetry(play_telemetry=play_controller.telemetry)

        if state == None:
            self._state = play_controller.play_config.state_waiting()
        else:
            self._state = state(**state_args)

    def run(self):
        # new_state_args is a dict of args to be handed to new_state on instantiation
        instance_action, new_state, new_state_args = self._state.check_exit(self)
        if instance_action == STATE_STAY:
            log.log(9, "STATE_STAY")
            return
        elif instance_action == STATE_MOVE:
            log.log(10, "STATE_MOVE from {self.state} to {new_state}")
            self.state = new_state
            return
        elif instance_action == STATE_SPLIT:
            log.log(10, "STATE_SPLIT")
            # to split means to leave this instance where it is, and spawn a new instance at
            # whatever the next state is
            # for example, a partial fill on a limit buy. in that case, the existing instance would continue on until 100% fill or cancel
            # but a new instance would be spawned to handle the partially filled units
            # to do that, it needs to know how many got filled
            # and it needs a copy of the order so it knows details like order type, filled price etc
            # new instance is instantiated using fill information from broker api, gets a new sub-identifier and gets a new telemetry object
            # new instance continues on
            # TODO which instance owns the fees?
            self.parent_controller.fork_instance(self, new_state, **new_state_args)

        else:
            raise NotImplementedError("This should never happen...")

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


class InstanceController(ABC):
    def __init__(
        self,
        symbol: Symbol,
        play_config: ControllerConfig,
        play_instance_class: Instance = Instance,
    ) -> None:
        self.symbol = symbol
        self.play_config = play_config
        self.play_id = self._generate_play_id()
        # PlayInstance class to be use - can be overridden to enable extension
        self.play_instance_class = play_instance_class
        self.instances = []
        self.telemetry = ControllerTelemetry()

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

    def fork_instance(self, instance: Instance, new_state: State, **kwargs):
        kwargs["previous_state"] = instance.state
        self.instances.append(
            self.play_instance_class(
                template=instance.config, play_controller=self, state=new_state, state_args=kwargs
            )
        )


# TODO
# instance play changes implementations                 ?????
# create instance telemetry methods
# create play telemetry methods
# hook up play and instance telemetry callbacks
