from .state import State
from abc import abstractmethod
from math import floor
from symbol import InvalidQuantity, InvalidPrice
import logging

log = logging.getLogger(__name__)


class StateEnteringPosition(State):
    _cls_str = "IStateEnteringPosition"

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

        log_extras = {}
        log_extras["buy_order_overridden"] = True
        log_extras["default_limit_price"] = False
        log_extras["default_unit_quantity"] = False
        log_extras["notional"] = True

        # allow this to be overridden by passing it in to init, otherwise fall back to config
        order_type = kwargs.get("type", None)
        if not order_type:
            order_type = self.config.buy_order_type
            self.log.debug(f"Using default order type of {self.config.buy_order_type}")
            log_extras["buy_order_overridden"] = False

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
            log_extras["default_limit_price"] = True

        elif limit_specified:
            # make sure they aligned quantity
            aligned_limit_price = self.symbol.align_price(limit_specified)
            if aligned_limit_price != limit_specified:
                self.log.error(
                    f"Call <symbol>.align_price() before submitting a buy order"
                )
                raise InvalidPrice(
                    f"Call <symbol>.align_price() before submitting a buy order"
                )

        units = kwargs.get("units")
        if not units:
            _bars = self.ohlc.get_latest()
            last_price = _bars.Close
            budget = self.config.max_play_size
            units = budget / last_price
            self.log.debug(
                f"No units set, using default calculation. Unaligned units: {units}"
            )
            log_extras["default_unit_quantity"] = True
            log_extras["units_raw"] = units

        if not self.symbol.notional_units:
            log_extras["notional"] = False
            log_extras["units_before_notional_rounding"] = units
            units = floor(units)
            self.log.debug(
                f"Notional units are not enabled. Rounding units down to {units}"
            )

        try:
            # can throw error for insufficient units
            aligned_units = self.symbol.align_quantity(units)
            self.log.debug(f"Aligned units is {aligned_units}")
            log_extras["units_aligned"] = aligned_units
        except Exception as e:
            self.log.exception(f"Failed to align units: {str(e)}")
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
                self.log.debug(
                    f"Successfully submitted {order.order_type_text} for {aligned_units} units at {aligned_limit_price}"
                )

            except Exception as e:
                self.log.exception(
                    f"Failed to submit Buy Limit order for {aligned_units} units at {aligned_limit_price}. Error: {str(e)}",
                )
                raise

        else:
            try:
                order = self.parent_instance.buy_market(units=aligned_units)
                self.log.debug(
                    f"Successfully submitted {order.order_type_text} for {aligned_units} units"
                )

            except Exception as e:
                self.log.exception(
                    f"Failed to submit Buy Market order for {aligned_units}. Error: {str(e)}",
                )
                raise

        # hold on to the order result object for further inspection in check_exit and do_exit
        self.intervals_until_timeout = self.config.buy_timeout_intervals
        self.log.debug(
            f"Set buy order timeout interval of {self.config.buy_timeout_intervals} intervals"
        )

        log_extras["order_type"] = order.order_type_text
        log_extras["order_status_summary"] = order.status_summary
        log_extras["order_status_detail"] = order.status_text
        log_extras["order_timeout"] = self.config.buy_timeout_intervals

        self.log.info(
            f"Buy order submitted", state_parameters=log_extras, order=order.as_dict()
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
            log_extras = {"next_state": taking_profit_state.__name__}
            self.log.info(
                f"Buy order filled", state_parameters=log_extras, order=order.as_dict()
            )

            return State.STATE_MOVE, taking_profit_state, {}

        elif order.status_summary == "open" or order.status_summary == "pending":
            self.intervals_until_timeout -= 1

            if self.intervals_until_timeout == 0:
                terminated_state = self.controller.play_config.state_terminated
                self.log.info(
                    f"{self.parent_instance}: Order ID {order_id} has timed out, moving to {terminated_state.__name__}"
                )
                log_extras = {"next_state": terminated_state.__name__}
                self.log.info(
                    f"Buy order timed out",
                    state_parameters=log_extras,
                    order=order.as_dict(),
                )
                return State.STATE_MOVE, terminated_state, {}

            else:
                last_close = self.ohlc.get_latest().Close
                entry_price = order.ordered_unit_price
                self.log.info(
                    f"Order ID {order_id} is still in state {order.status_summary}. Last close {last_close} vs entry price {entry_price}"
                )
                self.log.info("Buy order still open", order=order.as_dict())

                return State.STATE_STAY, None, {}

        elif order.status_summary == "cancelled":
            terminated_state = self.controller.play_config.state_terminated
            log.info(
                f"{self.parent_instance}: Order ID {order_id} has been cancelled, moving to {terminated_state.__name__}"
            )
            log_extras = {"next_state": terminated_state.__name__}
            self.log.info(
                "Buy order still open",
                state_parameters=log_extras,
                order=order.as_dict(),
            )

            return State.STATE_MOVE, terminated_state, {}

        else:
            print("wut")
