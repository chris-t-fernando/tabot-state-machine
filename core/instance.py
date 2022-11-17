from abc import ABC
from datetime import datetime
import uuid

from .play_config import PlayConfig
from .shonky_log import ShonkyLog
from .state import State
from .state_terminated import StateTerminated
from .state_stopping_loss import StateStoppingLoss
from .state_taking_profit import StateTakingProfit
from .time_manager import ITimeManager
from broker_api import IOrderResult
from .exceptions import BuyOrderAlreadySet, SellOrderAlreadySet

from pythonjsonlogger import jsonlogger
from logbeam import CloudWatchLogsHandler
import logging

log = logging.getLogger(__name__)


class Instance(ABC):
    _state: State

    def __init__(
        self, template: PlayConfig, play_controller, state=None, state_args=None
    ) -> None:
        self.config = template
        self.parent_controller = play_controller
        self.time_manager = play_controller.time_manager
        self.broker = play_controller.broker
        self.symbol = play_controller.symbol
        self.ohlc = play_controller.symbol.ohlc
        self.symbol_str = play_controller.symbol.yf_symbol
        self.start_timestamp = datetime.utcnow()
        self.started = True
        self._entry_price = None
        self._stop_price = None
        self._target_price = None
        self._buy_order = None
        self._active_sales_order = None
        self._sales_orders = {}
        log_group = "tabot-state-machine"
        unique_id = self._generate_id()
        self.id = f"{self.symbol_str}-{self.config.name}-{unique_id}"
        instance_log = logging.getLogger(self.id)
        # instance_log.propagate = False
        format_str = "%(levelname)%(message)"
        formatter = jsonlogger.JsonFormatter(format_str)
        self.handler = CloudWatchLogsHandler(
            log_group_name=log_group,
            log_stream_name=self.id,
            buffer_duration=10000,
            batch_count=100,
        )
        self.handler.setFormatter(formatter)
        instance_log.setLevel(logging.DEBUG)
        instance_log.addHandler(self.handler)

        self.log = ShonkyLog(instance_log)

        if state == None:
            self._state = play_controller.play_config.state_waiting(
                parent_instance=self
            )
        else:
            self._state = state(**state_args)

    def __repr__(self):
        return self.id

    def _generate_id(self, length: int = 6):
        return "instance-" + uuid.uuid4().hex[:length].upper()

    def run(self):
        # loop until the answer comes back to stay put
        while True:
            # new_state_args is a dict of args to be handed to new_state on instantiation
            instance_action, new_state, new_state_args = self._state.check_exit()
            if instance_action == State.STATE_STAY:
                self.log.log(9, "STATE_STAY")
                break

            elif instance_action == State.STATE_MOVE:
                self.log.log(9, f"STATE_MOVE from {self.state} to {new_state}")
                self.state = new_state

            elif instance_action == State.STATE_SPLIT:
                self.log.log(9, "STATE_SPLIT")
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

    def stop(self, hard_stop: bool = False):
        self.log.info(f"Stopping instance {self} (hard_stop: {hard_stop})")
        state = self.state
        if isinstance(state, StateTerminated):
            # nothing to do
            self.log.info(f"Can't stop instance {self} - already in Terminated state")
        elif isinstance(state, StateStoppingLoss) or isinstance(
            state, StateTakingProfit
        ):
            if hard_stop:
                self.log.warning(f"Hard stopping {self}")
                self.state = self.parent_controller.play_config.state_terminated
            else:
                self.log.info(f"Instance {self} is in state {state} - skipping stop")
        else:
            # fair game
            self.log.info(f"Stopping {self}")
            self.state = self.parent_controller.play_config.state_terminated

        self.started = False

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, new_state):
        if not isinstance(new_state, type):
            _msg = f"Specified state '{new_state}' must be a class"
            self.log.error(_msg)
            raise RuntimeError(_msg)

        self._state.do_exit()
        self.log.log(9, f"do_exit() successful on {self._state}")

        self._state = new_state(previous_state=self._state)
        self.log.log(9, f"successfully set new state to {self._state}")

    @property
    def stop_loss_price(self):
        return self._stop_price

    @stop_loss_price.setter
    def stop_loss_price(self, new_stop_loss_price):
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
        if self._buy_order == None:
            return 0
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
    def total_buy_value(self):
        if not self.buy_order:
            return 0

        if not self.buy_order.filled_total_value:
            return 0

        return self.buy_order.filled_total_value

    @property
    def total_sell_value(self):
        earned = 0
        for order_id, order in self._sales_orders.items():
            if order.filled_total_value:
                earned += order.filled_total_value
        return earned

    @property
    def total_gain(self):
        gain = self.total_buy_value - self.total_sell_value
        return gain

    @property
    def open_sales_order(self):
        # if there's no active sale order
        if not self._active_sales_order:
            return None

        # otherwise refresh it and return it
        existing_order = self._sales_orders[self._active_sales_order.order_id]
        self._active_sales_order = self.broker.get_order(existing_order.order_id)
        # filled sales order to be updated here
        if self._active_sales_order.status_text == "filled":
            self._sales_orders[existing_order.order_id] = self._active_sales_order

        return self._active_sales_order

    @open_sales_order.setter
    def open_sales_order(self, new_order: IOrderResult):
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
            self.log.warning(
                f"Stop loss triggered",
                state_parameters={
                    "last_close": last_close,
                    "stop loss": self.stop_loss_price,
                },
            )
            return True
        self.log.log(
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
