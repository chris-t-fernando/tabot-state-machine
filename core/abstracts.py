from abc import ABC, abstractmethod
from symbol.symbol import Symbol, InvalidQuantity, InvalidPrice
from symbol.symbol_data import SymbolData
from datetime import datetime
import uuid
import logging
from math import floor
from broker_api.ibroker_api import ITradeAPI, IOrderResult
from cloudwatch import cloudwatch

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


class UnhandledBrokerException(Exception):
    ...


class BuyOrderAlreadySet(Exception):
    ...


class SellOrderAlreadySet(Exception):
    ...


class InvalidTakeProfit(Exception):
    ...


class InstanceTemplate(ABC):
    def __init__(
        self,
        name: str,
        buy_signal_strength: float,
        take_profit_risk_multiplier: float,
        take_profit_pct_to_sell: float,
        stop_loss_trigger_pct: float,
        stop_loss_type: str = "market",
        stop_loss_hold_intervals: int = 1,
        buy_order_type: str = "limit",
        buy_timeout_intervals: int = 2,
    ) -> None:
        self.name = name
        self.buy_signal_strength = buy_signal_strength
        self.buy_order_type = buy_order_type
        self.take_profit_risk_multiplier = take_profit_risk_multiplier
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
    log: logging.Logger

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
        self.controller = self.parent_instance.parent_controller
        self.log = self.parent_instance.log

    @abstractmethod
    def check_exit(self):
        self.log.log(9, f"Started check_exit on {self.__repr__()}")
        # log.log(9, f"Started check_exit on {self.__repr__()}")

    def do_exit(self):
        self.log.log(9, f"Finished do_exit on {self.__repr__()}")

    def __del__(self):
        # use this to make sure that open orders are cancelled?
        self.log.log(9, f"Deleting {self.__repr__()}")

    def __repr__(self) -> str:
        return self.__class__.__name__


class IStateWaiting(State):
    @abstractmethod
    def __init__(self, previous_state: State, parent_instance=None) -> None:
        super().__init__(parent_instance=parent_instance, previous_state=previous_state)


class IStateEnteringPosition(State):
    @abstractmethod
    def __init__(self, previous_state: State, parent_instance=None, **kwargs) -> None:
        super().__init__(parent_instance=parent_instance, previous_state=previous_state)

        # default behaviour is to put in a limit price at the last close price
        # options:
        #  - order_type to specify a limit or market buy order type. Default is 'limit'
        #  - limit_price to specify the limit price, if limit order is used. Default is last close
        #  - units to specify number of units to purchase. Defaults:
        #    - for 'limit' orders, config.buy_budget / limit_price
        #    - for 'market' orders, config.buy_budget / last close price

        # allow this to be overridden by passing it in to init, otherwise fall back to config
        order_type = kwargs.get("type", None)
        if not order_type:
            order_type = self.config.buy_order_type
            self.log.debug(f"Using default order type of {self.config.buy_order_type}")

        # boolean checks to see if we need to generate a limit price
        limit_specified = kwargs.get("limit_price")
        generate_limit = not limit_specified and order_type == "limit"

        if generate_limit:
            _bars = self.ohlc.get_latest()
            limit_price = _bars.Close
            aligned_limit_price = self.symbol.align_price(limit_price)
            self.log.debug(
                f"No limit price set, using default calculated limit price of {aligned_limit_price}"
            )

        elif limit_specified:
            # make sure they aligned quantity
            aligned_limit_price = self.symbol.align_price(limit_specified)
            if aligned_limit_price != limit_specified:
                self.log.error(f"Call <symbol>.align_price() before submitting a buy order")
                raise InvalidPrice(f"Call <symbol>.align_price() before submitting a buy order")

        units = kwargs.get("units")
        if not units:
            _bars = self.ohlc.get_latest()
            last_price = _bars.Close
            budget = self.config.buy_budget
            units = budget / last_price
            self.log.debug(f"No units set, using default calculation. Unaligned units: {units}")

        if not self.symbol.notional_units:
            units = floor(units)
            self.log.debug(f"Notional units are not enabled. Rounding units down to {units}")

        try:
            # can throw error for insufficient units
            aligned_units = self.symbol.align_quantity(units)
            self.log.debug(f"Aligned units is {aligned_units}")
        except Exception as e:
            self.log.error(f"Failed to align units: {str(e)}")
            raise

        # this is my own validation - make sure that the units ordered = the units after rounding
        if aligned_units != units:
            _message = f"Call <symbol>.align_quantity() before submitting a buy order. Requested {units}, aligned to {aligned_units}"
            self.log.error(_message)
            raise InvalidQuantity(_message)

        # try:
        if order_type == "limit":
            try:
                order = self.parent_instance.buy_limit(
                    units=aligned_units, unit_price=aligned_limit_price
                )
                self.log.info(
                    f"Successfully submitted {order.order_type_text} for {aligned_units} units at {aligned_limit_price}"
                )

            except Exception as e:
                self.log.error(
                    f"Failed to submit Buy Limit order for {aligned_units} units at {aligned_limit_price}. Error: {str(e)}"
                )

        else:
            try:
                order = self.parent_instance.buy_market(units=aligned_units)
                self.log.info(
                    f"Successfully submitted {order.order_type_text} for units {aligned_units}"
                )
            except Exception as e:
                self.log.error(
                    f"Failed to submit Buy Market order for {aligned_units}. Error: {str(e)}"
                )

        # hold on to the order result object for further inspection in check_exit and do_exit
        self.intervals_until_timeout = self.config.buy_timeout_intervals
        self.log.debug(
            f"Set buy order timeout interval of {self.config.buy_timeout_intervals} intervals"
        )

    def check_exit(self):
        super().check_exit()

        # check if order is still open / dead / partially filled
        # depending on this, return different options
        order_id = self.parent_instance.buy_order.order_id

        # get the order from the broker
        order = self.parent_instance.get_order(order_id)

        # TODO status summary needs to cater for partial fills, and then this logic does too
        if order.status_summary == "filled":
            # fully filled
            self.parent_instance.buy_order = order
            taking_profit_state = self.controller.play_config.state_taking_profit
            _order_type = order.order_type_text
            _filled_units = order.filled_unit_quantity
            _filled_price = order.filled_unit_price
            self.log.info(
                f"{_order_type} order ID {order_id} for {_filled_units} at {_filled_price} has been filled, moving to {taking_profit_state}"
            )

            return State.STATE_MOVE, taking_profit_state, {}

        elif order.status_summary == "open" or order.status_summary == "pending":
            self.intervals_until_timeout -= 1

            if self.intervals_until_timeout == 0:
                terminated_state = self.controller.play_config.state_terminated
                log.info(
                    f"{self.parent_instance}: Order ID {order_id} has timed out, moving to {terminated_state}"
                )
                return State.STATE_MOVE, terminated_state, {}

            else:
                last_close = self.ohlc.get_latest().Close
                entry_price = order.ordered_unit_price
                log.info(
                    f"Order ID {order_id} is still in state {order.status_summary}. Last close {last_close} vs entry price {entry_price}"
                )
                return State.STATE_STAY, None, {}

        elif order.status_summary == "cancelled":
            terminated_state = self.controller.play_config.state_terminated
            log.info(
                f"{self.parent_instance}: Order ID {order_id} has been cancelled, moving to {terminated_state}"
            )
            return State.STATE_MOVE, terminated_state, {}

        else:
            print("wut")


class IStateTakingProfit(State):
    @abstractmethod
    def __init__(self, previous_state: State, parent_instance=None, **kwargs) -> None:
        super().__init__(parent_instance=parent_instance, previous_state=previous_state)

        if kwargs.get("units_to_sell", None):
            units_to_sell = kwargs["units_to_sell"]
            log.log(9, f"Finding units to sell via class {self}")
        else:
            units_to_sell = self._default_units_to_sell()
            log.log(9, f"Finding units to sell via default base class")

        if kwargs.get("target_unit", None):
            target_unit = kwargs["target_unit"]
            log.log(9, f"Finding unit target price to sell via class {self}")
        else:
            target_unit = self._default_unit_price()
            log.log(9, f"Finding unit price via default base class")

        # TODO add validation - zero units, zero price, price lower than buy price
        sell_order = self.parent_instance.sell_limit(units=units_to_sell, unit_price=target_unit)
        log.debug(f"Sell limit order submitted for {units_to_sell} units at {target_unit}")

    def _default_units_to_sell(self):
        sell_pct = self.config.take_profit_pct_to_sell
        held = self.parent_instance.units_held
        units_to_sell_unaligned = sell_pct * held
        units_to_sell = self.symbol.align_quantity_increment(units_to_sell_unaligned)
        return units_to_sell

    def _default_unit_price(self):
        # risk = entry unit price - stop unit price
        entry_unit = self.parent_instance.entry_price
        stop_unit = self.parent_instance.stop_loss_price
        risk_unit = entry_unit - stop_unit
        multiplier = self.parent_instance.take_profit_multiplier

        if risk_unit < 0:
            # not great hack - happens when you do a buy market and the spread sucks
            risk_unit = self.symbol.align_price(stop_unit - entry_unit)
            log.error(
                f"Base class unit price default: Risk unit is < 0 - probably because the Market buy filled unit price is lower than the set stop loss price. Overrode to {risk_unit}"
            )
            # raise InvalidTakeProfit(f"Target price of {} is lower than stop")

        # target profit = 1.5 * risk * number of times we've taken profit already
        trigger_risk_multiplier = self.config.take_profit_risk_multiplier
        target_unit_profit = trigger_risk_multiplier * risk_unit * multiplier

        # target price = entry price + target profit
        target_unit_unaligned = entry_unit + target_unit_profit
        target_unit = self.symbol.align_price(target_unit_unaligned)

        return target_unit

    def check_exit(self):
        super().check_exit()

        # TODO this bit next
        # check that stop loss hasn't been hit first
        if self.parent_instance.stop_loss_triggered():
            stop_loss_state = self.controller.play_config.state_stopping_loss
            return State.STATE_MOVE, stop_loss_state, {}

        order = self.parent_instance.open_sales_order
        sale_status = order.status_summary
        sale_id = order.order_id

        if sale_status == "filled":
            # filled but don't hold any more, so bail
            if self.parent_instance.units_held == 0:
                terminated_state = self.controller.play_config.state_terminated
                log.info(
                    f"Take profit order ID {sale_id} has been filled. No units still held, so moving to state {terminated_state}"
                )
                return State.STATE_MOVE, terminated_state, {}

            # filled and still hold more, so take profit again
            taking_profit_state = self.controller.play_config.state_taking_profit
            log.info(
                f"Take profit order ID {sale_id} has been filled, repeating state {taking_profit_state}"
            )
            return State.STATE_MOVE, taking_profit_state, {}

        elif sale_status == "cancelled":
            # something happened - what do we do?
            terminated_state = self.controller.play_config.state_terminated
            log.error(
                f"{self.parent_instance}: Take profit order ID {sale_id} has been cancelled outside of state machine control, moving to {terminated_state}"
            )
            return State.STATE_MOVE, terminated_state, {}

        else:
            last_close = self.symbol.align_price(self.parent_instance.ohlc.get_latest().Close)
            log.log(
                9,
                f"Take profit order ID {sale_id} is still open (target price {order.ordered_unit_price} vs last close {last_close}), staying in state {self}",
            )
            return State.STATE_STAY, None, {}

    def do_exit(self):
        return super().do_exit()


class IStateStoppingLoss(State):
    @abstractmethod
    # def __init__(self, parent_instance, previous_state: State) -> None:
    def __init__(self, previous_state: State, parent_instance=None) -> None:
        super().__init__(parent_instance=parent_instance, previous_state=previous_state)

    def check_exit(self):
        super().check_exit()
        terminated_state = self.controller.play_config.state_terminated
        log.debug(
            f"{self.parent_instance}: No default clean activities, moving straight to {terminated_state}"
        )
        return State.STATE_MOVE, terminated_state, {}


class IStateTerminated(State):
    @abstractmethod
    # def __init__(self, parent_instance, previous_state: State) -> None:
    def __init__(self, previous_state: State, parent_instance=None, **kwargs) -> None:
        super().__init__(parent_instance=parent_instance, previous_state=previous_state)

        # collect orders to be cancelled
        if kwargs.get("cancel_orders", None):
            cancel_orders = kwargs["cancel_orders"]
        else:
            cancel_orders = []

        if self.parent_instance.buy_order != None:
            order_id = self.parent_instance.buy_order.order_id
            order = self.parent_instance.get_order(order_id)

            if not order.closed:
                cancel_orders.append(order_id)

        if self.parent_instance.open_sales_order:
            if not self.parent_instance.open_sales_order.closed:
                cancel_orders.append(self.parent_instance.open_sales_order.order_id)

        # cancel orders
        log.debug(f"Found {len(cancel_orders)} open orders to cancel")
        for _order_id in cancel_orders:
            cancel_order = self.parent_instance.cancel_order(_order_id)

            if not cancel_order.closed:
                raise UnhandledBrokerException(
                    f"Failed to cancel {cancel_order.order_type_text} order ID {_order_id}. State is {cancel_order.status_text}"
                )
            log.debug(f"Successfully cancelled order {_order_id}")

        log.info(f"Successfully cancelled {len(cancel_orders)} orders")

        # if the instance still holds units, liquidate them
        if self.parent_instance.units_held > 0:
            # validate it, just in case
            log.debug(f"Instance still holds {self.parent_instance.units_held} units - liquidating")
            units = self.symbol.align_quantity_increment(self.parent_instance.units_held)
            liquidate_order = self.parent_instance.sell_market(units)

            if not liquidate_order.closed:
                liquidate_id = liquidate_order.order_id
                liquidate_status = liquidate_order.status_text
                raise UnhandledBrokerException(
                    f"Failed to {order.order_type_text} {units} units. Order ID was {liquidate_id}. State is {liquidate_status}"
                )

            log.info(
                f"Successfully liquidated instance holding of {liquidate_order.filled_unit_quantity} units"
            )

        self.parent_instance.handler.close()


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
        self._entry_price = None
        self._stop_price = None
        self._target_price = None
        self._buy_order = None
        self._active_sales_order = None
        self._sales_orders = {}
        log_name = f"{self.symbol_str}-{self.config.name}"
        stream_name = self._generate_id()
        self.log = logging.getLogger(f"{log_name}-{stream_name}")
        self.log.propagate = False
        formatter = logging.Formatter("%(asctime)s : %(levelname)s - %(message)s")
        self.handler = cloudwatch.CloudwatchHandler(
            log_group=log_name, log_stream=stream_name, retention_period=7
        )
        self.handler.setFormatter(formatter)
        self.log.setLevel(logging.DEBUG)
        self.log.addHandler(self.handler)

        if state == None:
            self._state = play_controller.play_config.state_waiting(parent_instance=self)
        else:
            self._state = state(**state_args)

    def _generate_id(self, length: int = 6):
        return "instance-" + uuid.uuid4().hex[:length].upper()

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
    def stop_loss_price(self):
        return self._stop_price

    @stop_loss_price.setter
    def stop_loss_price(self, new_stop_loss_price):
        # TODO add in telemetry hook
        aligned_stop_price = self.symbol.align_price(new_stop_loss_price)
        self._stop_price = aligned_stop_price

    @property
    def buy_order(self):
        return self._buy_order

    @buy_order.setter
    def buy_order(self, order: IOrderResult):
        if self._buy_order != None and self._buy_order.order_id != order.order_id:
            raise BuyOrderAlreadySet(
                f"Attempted to set buy_order property to {order.order_id}, but it was already set to {self._buy_order.order_id}"
            )

        if order.closed:
            self._entry_price = order.filled_unit_price

        self._buy_order = order

    @property
    def units_bought(self):
        filled = self._buy_order.filled_unit_quantity
        # if none are filled, this will be None
        if not filled:
            filled = 0
        return filled

    @property
    def units_sold(self):
        units_sold = 0
        for sale_id in self.filled_sales_orders:
            units_sold += self.filled_sales_orders[sale_id].filled_unit_quantity

        return units_sold

    @property
    def total_spent(self):
        if not self.buy_order:
            return 0

        if not self.buy_order.filled_total_value:
            return 0

        return self.buy_order.filled_total_value

    @property
    def total_earned(self):
        earned = 0
        for order_id, order in self._sales_orders.items():
            if order.filled_total_value:
                earned += order.filled_total_value
        return earned

    @property
    def total_gain(self):
        gain = self.total_earned - self.total_spent
        if gain < -150:
            print("bananas")
        return self.total_earned - self.total_spent

    @property
    def open_sales_order(self):
        # if there's no active sale order
        if not self._active_sales_order:
            return None

        # otherwise refresh it and return it
        existing_order = self._sales_orders[self._active_sales_order.order_id]
        self._active_sales_order = self.broker.get_order(existing_order.order_id)
        return self._active_sales_order

    @open_sales_order.setter
    def open_sales_order(self, new_order):
        if self._active_sales_order != None:
            # there's already a sales order. check if its filled or not
            existing_order = self.open_sales_order

            # the existing sales order isn't closed yet, so can't move on to raising a new one..
            if not existing_order.closed:
                raise SellOrderAlreadySet(
                    f"Cannot open new sales order for this Instance, since existing sales order {existing_order.order_id} is still in state {existing_order.status_summary}"
                )

        self._active_sales_order = new_order

        # for sale_id in self._sales_orders:
        #    if self._sales_orders[sale_id].closed == False:
        #        open_orders[sale_id] = self._sales_orders[sale_id]
        # return open_orders

    def stop_loss_triggered(self):
        last_close = self.symbol.align_price(self.ohlc.get_latest().Close)
        if last_close < self.stop_loss_price:
            log.warning(
                f"Stop loss triggered. Last close was {last_close} vs stop loss of {self.stop_loss_price}"
            )
            return True
        log.log(
            9,
            f"Stop loss was not triggered. Last close was {last_close} vs stop loss of {self.stop_loss_price}",
        )
        return False

    @property
    def filled_sales_orders(self):
        filled_orders = {}
        for sale_id in self._sales_orders:
            if self._sales_orders[sale_id].status_summary == "filled":
                filled_orders[sale_id] = self._sales_orders[sale_id]
        return filled_orders

    @property
    def units_held(self):
        return self.units_bought - self.units_sold

    @property
    def take_profit_multiplier(self):
        multiplier = 1
        multiplier += len(self.filled_sales_orders)
        return multiplier

    @property
    def buy_order_id(self):
        return self._buy_order.order_id

    @property
    def entry_price(self):
        return self._entry_price

    def add_sell_order(self, order: IOrderResult):
        self.open_sales_order = order
        self._sales_orders[order.order_id] = order

    # just basic passthrough
    # TODO telemetry stuff
    def buy_limit(self, units: float, unit_price: float):
        order = self.broker.buy_order_limit(
            symbol=self.symbol_str, units=units, unit_price=unit_price
        )
        self.buy_order = order
        return order

    def buy_market(self, units: float):
        order = self.broker.buy_order_market(symbol=self.symbol_str, units=units)
        self.buy_order = order
        return order

    def sell_limit(self, units: float, unit_price: float):
        order = self.broker.sell_order_limit(
            symbol=self.symbol_str, units=units, unit_price=unit_price
        )
        self.add_sell_order(order)
        return order

    def sell_market(self, units: float):
        order = self.broker.sell_order_market(symbol=self.symbol_str, units=units)
        self.add_sell_order(order)
        return order

    def cancel_order(self, order_id: str):
        cancel_order = self.broker.cancel_order(order_id)
        # update our cache of orders with this status
        if cancel_order.order_type_text.find("SELL") > -1:
            self.add_sell_order(cancel_order)

        return cancel_order

    def get_order(self, order_id: str):
        order = self.broker.get_order(order_id)
        # update our cache of orders with this status
        if order.order_type_text.find("SELL") > -1:
            self.add_sell_order(order)

        return order


class InstanceList:
    def __init__(self) -> None:
        self.instances = []

    def append(self, new_instance):
        self.instances.append(new_instance)

    @property
    def total_gain(self):
        gain = 0
        for i in self.instances:
            gain += i.total_gain
        return gain


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

    @property
    def gain(self):
        gain = 0
        for i in self.instances:
            if i.total_earned != 0:
                gain += i.total_gain
                # print(f"\t\t{i}\t{i.total_gain}")
            else:
                log.debug(
                    f"Ignoring instance {i} since it has not taken profit or stopped loss yet"
                )

        return gain

    def run(self):
        new_instances = []
        retained_instances = []
        for i in self.instances:
            i.run()

            if isinstance(i.state, IStateTerminated):
                # if this instance is terminated, spin up a new one
                self.terminated_instances.append(i)
                new_instances.append(self.play_instance_class(i.config, self))
                gain = self.gain
                print(f"Total gain for this symbol: {gain:,.2f}")

            else:
                retained_instances.append(i)

        updated_instances = new_instances + retained_instances
        self.instances = updated_instances

        # self.get_instances(self.instances[0].config)

    def fork_instance(self, instance: Instance, new_state: State, **kwargs):
        kwargs["previous_state"] = instance.state
        self.instances.append(
            self.play_instance_class(
                template=instance.config, play_controller=self, state=new_state, state_args=kwargs
            )
        )

    def get_instances(self, template: InstanceTemplate):
        all_instances = self.instances + self.terminated_instances
        matched_instances = InstanceList()
        for i in all_instances:
            if i.config == template:
                matched_instances.append(i)

        return matched_instances


# TODO
# split logging
# ingest logging to CloudWatch
# create Orchestrator
