from .state import State
from .exceptions import UnhandledBrokerException


class StateTerminated(State):
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
        self.log.debug(f"Found {len(cancel_orders)} open orders to cancel")
        for _order_id in cancel_orders:
            cancel_order = self.parent_instance.cancel_order(_order_id)

            if not cancel_order.closed:
                raise UnhandledBrokerException(
                    f"Failed to cancel {cancel_order.order_type_text} order ID {_order_id}. State is {cancel_order.status_text}"
                )
            self.log.debug(
                f"Successfully cancelled order {_order_id}",
                order=cancel_order.as_dict(),
            )

        self.log.info(f"Successfully cancelled {len(cancel_orders)} orders")

        # if the instance still holds units, liquidate them
        if self.parent_instance.units_held > 0:
            # validate it, just in case
            self.log.debug(
                f"Instance still holds {self.parent_instance.units_held} units - liquidating"
            )
            units = self.symbol.align_quantity_increment(
                self.parent_instance.units_held
            )
            liquidate_order = self.parent_instance.sell_market(units)

            if not liquidate_order.closed:
                liquidate_id = liquidate_order.order_id
                liquidate_status = liquidate_order.status_text
                raise UnhandledBrokerException(
                    f"Failed to {order.order_type_text} {units} units. Order ID was {liquidate_id}. State is {liquidate_status}"
                )

            self.log.info(f"Liquidated instance", order=liquidate_order.as_dict())

        # TODO all this telemetry should be done in instance
        _sell_value = self.parent_instance.total_sell_value
        _buy_value = self.parent_instance.total_buy_value
        _gained = _sell_value - _buy_value
        _buy_units = self.parent_instance.units_bought
        _avg_buy_price = 0 if _buy_value == 0 else _buy_value / _buy_units
        _avg_sell_price = 0 if _sell_value == 0 else _sell_value / _buy_units
        _buy_order_count = 1 if self.parent_instance.buy_order else 0
        _sell_order_count = len(self.parent_instance._sales_orders)
        _sell_order_filled_count = len(self.parent_instance.filled_sales_orders)

        log_extras = {
            "run_id": self.parent_instance.parent_controller.run_id,
            "weather_condition": self.parent_instance.parent_controller.play_config.market_condition,
            "symbol": self.symbol,
            "symbol_group": self.parent_instance.parent_controller.play_config.symbol_category,
            "play_config_name": self.parent_instance.parent_controller.play_config.name,
            "units": _buy_units,
            "bought_value": _buy_value,
            "sold_value": _sell_value,
            "total_gain": _gained,
            "average_buy_price": _avg_buy_price,
            "average_sell_price": _avg_sell_price,
            "buy_order_count": _buy_order_count,
            "sell_order_count": _sell_order_count,
            "sell_order_filled_count": _sell_order_filled_count,
            "instance_id": self.parent_instance.id,
        }

        if _sell_order_count > 0:
            log_level = 51
        else:
            log_level = 10
        self.log.log(log_level, f"Instance summary", state_parameters=log_extras)

        self.log.info(
            f"Instance termination complete at {self.parent_instance.time_manager.now}"
        )

        telemetry_message = log_extras.copy()
        telemetry_message["symbol"] = str(telemetry_message["symbol"])

        self.parent_instance.telemetry.emit(
            event="instance terminated", **telemetry_message
        )

        # self.parent_instance.handler.close()
