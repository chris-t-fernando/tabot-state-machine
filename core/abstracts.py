from abc import ABC, abstractmethod
from symbol.symbol import Symbol, InvalidQuantity, InvalidPrice
from symbol.symbol_data import SymbolData
from datetime import datetime
import uuid
import logging
from math import floor
from broker_api.ibroker_api import ITradeAPI

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


class InstanceTemplate(ABC):
    def __init__(
        self,
        name: str,
        buy_signal_strength: float,
        take_profit_trigger_pct_of_risk: float,
        take_profit_pct_to_sell: float,
        stop_loss_trigger_pct: float,
        stop_loss_type: str = "market",
        stop_loss_hold_intervals: int = 1,
        buy_timeout_intervals: int = 2,
    ) -> None:
        self.name = name
        self.buy_signal_strength = buy_signal_strength
        self.take_profit_trigger_pct_of_risk = take_profit_trigger_pct_of_risk
        self.take_profit_pct_to_sell = take_profit_pct_to_sell
        self.stop_loss_trigger_pct = stop_loss_trigger_pct
        self.stop_loss_type = stop_loss_type
        self.stop_loss_hold_intervals = stop_loss_hold_intervals
        self.buy_timeout_intervals = buy_timeout_intervals

    def __repr__(self) -> str:
        return f"<{type(self).__name__} '{self.name}'>"


class State(ABC):
    STATE_STAY = 0
    STATE_SPLIT = 1
    STATE_MOVE = 2

    symbol: Symbol
    symbol_str: str
    ohlc: SymbolData
    config: InstanceTemplate
    broker: ITradeAPI

    @abstractmethod
    def __init__(self, previous_state, parent_instance=None) -> None:
        log.debug(f"Started {self.__repr__()}")
        self.previous_state = previous_state
        if not parent_instance:
            self.parent_instance = previous_state.parent_instance
            config_source = previous_state
        else:
            self.parent_instance = parent_instance
            config_source = parent_instance

        self.symbol = config_source.symbol
        self.symbol_str = config_source.symbol_str
        self.ohlc = config_source.symbol.ohlc
        self.config = config_source.config
        self.broker = config_source.broker
        self.controller = self.parent_instance.parent_controller

        # self.ohlc = parent_instance.ohlc

    # @property
    # def ohlc(self) -> SymbolData:
    #    return self.parent_instance.ohlc

    # @property
    # def config(self) -> InstanceTemplate:
    #    return self.parent_instance.config

    # @ohlc.setter
    # def ohlc(self, ohlc_source):
    #    self.ohlc = ohlc_source

    @abstractmethod
    def check_exit(self):
        log.log(9, f"Started check_exit on {self.__repr__()}")

    def do_exit(self):
        log.log(9, f"Finished do_exit on {self.__repr__()}")

    def __del__(self):
        # use this to make sure that open orders are cancelled?
        log.log(9, f"Deleting {self.__repr__()}")

    def __repr__(self) -> str:
        return self.__class__.__name__

    @property
    def stop_loss_price(self):
        return self.parent_instance.stop_loss_price

    @stop_loss_price.setter
    def stop_loss_price(self, new_stop_loss_price):
        self.parent_instance.stop_loss_price = new_stop_loss_price


class IStateWaiting(State):
    @abstractmethod
    # def __init__(self, parent_instance, previous_state: State = None) -> None:
    def __init__(self, previous_state: State, parent_instance=None) -> None:
        super().__init__(parent_instance=parent_instance, previous_state=previous_state)


class IStateEnteringPosition(State):
    @abstractmethod
    # def __init__(self, parent_instance, previous_state: State) -> None:
    def __init__(self, previous_state: State, parent_instance=None, **kwargs) -> None:
        super().__init__(parent_instance=parent_instance, previous_state=previous_state)

        # default behaviour is to put in a limit price at the last close price
        # options:
        #  - order_type to specify a limit or market buy order type. Default is 'limit'
        #  - limit_price to specify the limit price, if limit order is used. Default is last close
        #  - units to specify number of units to purchase. Defaults:
        #    - for 'limit' orders, config.buy_budget / limit_price
        #    - for 'market' orders, config.buy_budget / last close price

        order_type = kwargs.get("type", "limit")

        # boolean checks to see if we need to generate a limit price
        limit_specified = kwargs.get("limit_price")
        generate_limit = not limit_specified and order_type == "limit"

        if generate_limit:
            _bars = self.ohlc.get_latest()
            limit_price = _bars.Close

            aligned_limit_price = self.symbol.align_price(limit_price)
        elif limit_specified:
            # make sure they aligned quantity
            aligned_limit_price = self.symbol.align_price(limit_specified)

            if aligned_limit_price != limit_specified:
                raise InvalidPrice(f"Call <symbol>.align_price() before submitting a buy order")

        units = kwargs.get("units")
        if not units:
            _bars = self.ohlc.get_latest()
            last_price = _bars.Close
            budget = self.config.buy_budget
            units = budget / last_price

        if not self.symbol.notional_units:
            units = floor(units)

        try:
            # can throw error for insufficient units
            aligned_units = self.symbol.align_quantity(units)
        except:
            raise

        # this is my own validation - make sure that the units ordered = the units after rounding
        if aligned_units != units:
            raise InvalidQuantity(f"Call <symbol>.align_quantity() before submitting a buy order")

        try:
            if order_type == "limit":
                order = self.broker.buy_order_limit(
                    symbol=self.symbol_str, units=aligned_units, unit_price=aligned_limit_price
                )
            else:
                order = self.broker.buy_order_market(symbol=self.symbol_str, units=units)

            # hold on to the order result object for further inspection in check_exit and do_exit
            self.order = order

        except Exception as e:
            # you need a way to either retry this or mark this object as tainted so that check_exit barfs
            print("Banana")

    def check_exit(self):
        super().check_exit()

        # check if order is still open / dead / partially filled
        # depending on this, return different options
        order_id = self.order.order_id

        # get the order from the broker
        order = self.broker.get_order(order_id)

        if order.status_summary == "filled":
            # fully filled
            taking_profit_state = self.controller.play_config.state_taking_profit
            log.info(f"Order ID {order_id} has been filled, moving to {taking_profit_state}")
            return State.STATE_MOVE, taking_profit_state, {}

        elif order.status_summary == "open" or order.status_summary == "pending":
            log.info(f"Order ID {order_id} is still in state {order.status_summary}")
            return State.STATE_STAY, None, {}

        elif order.status_summary == "cancelled":
            terminated_state = self.controller.play_config.state_terminated
            log.info(f"Order ID {order_id} has been cancelled, moving to {terminated_state}")
            return State.Move, terminated_state, {}

        else:
            print("wut")


class IStateTakingProfit(State):
    @abstractmethod
    # def __init__(self, parent_instance, previous_state: State) -> None:
    def __init__(self, previous_state: State, parent_instance=None) -> None:
        super().__init__(parent_instance=parent_instance, previous_state=previous_state)

    def check_exit(self):
        return super().check_exit()


class IStateStoppingLoss(State):
    @abstractmethod
    # def __init__(self, parent_instance, previous_state: State) -> None:
    def __init__(self, previous_state: State, parent_instance=None) -> None:
        super().__init__(parent_instance=parent_instance, previous_state=previous_state)


class IStateTerminated(State):
    @abstractmethod
    # def __init__(self, parent_instance, previous_state: State) -> None:
    def __init__(self, previous_state: State, parent_instance=None) -> None:
        super().__init__(parent_instance=parent_instance, previous_state=previous_state)


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
        self.broker = play_controller.broker
        self.symbol = play_controller.symbol
        self.ohlc = play_controller.symbol.ohlc
        self.symbol_str = play_controller.symbol.yf_symbol
        self.telemetry = InstanceTelemetry(play_telemetry=play_controller.telemetry)
        self.start_timestamp = datetime.utcnow()
        self._held_value = 0
        self._held_units = 0
        self._stop_price = None
        self._target_price = None
        self._buy_order_id = None
        self._sales_orders = None

        if state == None:
            self._state = play_controller.play_config.state_waiting(parent_instance=self)
        else:
            self._state = state(**state_args)

    def run(self):
        # loop until the answer comes back to stay put
        while True:
            # new_state_args is a dict of args to be handed to new_state on instantiation
            instance_action, new_state, new_state_args = self._state.check_exit()
            if instance_action == State.STATE_STAY:
                log.log(9, "STATE_STAY")
                break

            elif instance_action == State.STATE_MOVE:
                log.log(9, f"STATE_MOVE from {self.state} to {new_state}")
                self.state = new_state

            elif instance_action == State.STATE_SPLIT:
                log.log(9, "STATE_SPLIT")
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
        log.log(9, f"do_exit() successful on {self._state}")

        self._state = new_state(previous_state=self._state)
        log.log(9, f"successfully set new state to {self._state}")

    @property
    def held_units(self):
        return self._held_units

    @held_units.setter
    def held_units(self, new_units):
        # TODO add in telemetry hook
        self._held_units = new_units

    @property
    def stop_loss_price(self):
        return self._stop_price

    @stop_loss_price.setter
    def stop_loss_price(self, new_stop_loss_price):
        # TODO add in telemetry hook
        aligned_stop_price = self.symbol.align_price(new_stop_loss_price)
        self._stop_price = aligned_stop_price


class Controller(ABC):
    def __init__(
        self,
        symbol: Symbol,
        play_config: ControllerConfig,
        broker,
        play_instance_class: Instance = Instance,
    ) -> None:
        self.symbol = symbol
        self.play_config = play_config
        self._inject_common_config()
        self.play_id = self._generate_play_id()
        self.broker = broker
        # PlayInstance class to be use - can be overridden to enable extension
        self.play_instance_class = play_instance_class
        self.instances = []
        self.terminated_instances = []
        self.telemetry = ControllerTelemetry()

    def _inject_common_config(self):
        for template in self.play_config.play_templates:
            template.buy_budget = self.play_config.buy_budget

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
        new_instances = []
        retained_instances = []
        for i in self.instances:
            i.run()

            if isinstance(i.state, IStateTerminated):
                # if this instance is terminated, spin up a new one
                self.terminated_instances.append(i)
                new_instances.append(self.play_instance_class(i.config, self))
            else:
                retained_instances.append(i)

        updated_instances = new_instances + retained_instances
        self.instances = updated_instances

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
