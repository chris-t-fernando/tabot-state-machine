from .state import State
from abc import abstractmethod


class StateTakingProfit(State):
    @abstractmethod
    def __init__(self, previous_state: State, parent_instance=None, **kwargs) -> None:
        super().__init__(parent_instance=parent_instance, previous_state=previous_state)

        if kwargs.get("units_to_sell", None):
            units_to_sell = kwargs["units_to_sell"]
            self.log.log(9, f"Finding units to sell via class {self}")
        else:
            units_to_sell = self._default_units_to_sell()
            self.log.log(9, f"Finding units to sell via default base class")

        if kwargs.get("target_unit", None):
            target_unit = kwargs["target_unit"]
            self.log.log(9, f"Finding unit target price to sell via class {self}")
        else:
            target_unit = self._default_unit_price()
            self.log.log(9, f"Finding unit price via default base class")

        # TODO add validation - zero units, zero price, price lower than buy price
        sell_order = self.parent_instance.sell_limit(
            units=units_to_sell, unit_price=target_unit
        )

        log_extras = {"held_units": self.parent_instance.units_held}
        self.log.info(
            "Take profit sell order submitted",
            state_parameters=log_extras,
            order=sell_order.as_dict(),
        )

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
            self.log.error(
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
                log_extras = {
                    "held_units": self.parent_instance.units_held,
                    "next_state": terminated_state.__name__,
                }
                self.log.info(
                    f"Take profit order filled",
                    state_parameters=log_extras,
                    order=order.as_dict(),
                )

                return State.STATE_MOVE, terminated_state, {}

            # filled and still hold more, so take profit again
            taking_profit_state = self.controller.play_config.state_taking_profit
            log_extras = {
                "held_units": self.parent_instance.units_held,
                "next_state": taking_profit_state.__name__,
            }
            self.log.info(
                f"Take profit order filled",
                state_parameters=log_extras,
                order=order.as_dict(),
            )
            return State.STATE_MOVE, taking_profit_state, {}

        elif sale_status == "cancelled":
            # something happened - what do we do?
            terminated_state = self.controller.play_config.state_terminated
            log_extras = {
                "held_units": self.parent_instance.units_held,
                "next_state": taking_profit_state.__name__,
            }
            self.log.error(
                f"Take profit order cancelled",
                state_parameters=log_extras,
                order=order.as_dict(),
            )
            return State.STATE_MOVE, terminated_state, {}

        else:
            last_close = self.symbol.align_price(
                self.parent_instance.ohlc.get_latest().Close
            )
            log_extras = {
                "held_units": self.parent_instance.units_held,
                "next_state": None,
                "last_close": last_close,
            }

            self.log.log(
                9,
                f"Take profit order still open",
                state_parameters=log_extras,
                order=order.as_dict(),
            )
            return State.STATE_STAY, None, {}

    def do_exit(self):
        return super().do_exit()
