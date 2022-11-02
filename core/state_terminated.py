from abc import abstractmethod

from .state import State
from .exceptions import UnhandledBrokerException


class StateTerminated(State):
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

        _sold = self.parent_instance.total_sell_value
        _bought = self.parent_instance.total_buy_value
        _gained = _sold - _bought
        _units = self.parent_instance.units_bought
        _avg_buy_price = _bought / _units
        _avg_sell_price = _sold / _units

        log_extras = {
            "units": _units,
            "bought_value": _bought,
            "sold_value": _sold,
            "total_gain": _gained,
            "average_buy_price": _avg_buy_price,
            "average_sell_price": _avg_sell_price,
        }

        self.log.info(f"Instance summary", state_parameters=log_extras)
        self.log.info(f"Instance termination complete")
        self.parent_instance.handler.close()