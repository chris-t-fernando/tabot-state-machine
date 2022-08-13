class SalesOrders:
    def __init__(self, orders: dict):
        self.orders = orders
        self.keys = list(orders.keys())
        self.position = 0

    def __iter__(self):
        return self

    def __next__(self):
        return_key = self.keys[self.position]
        return_order = self.orders[return_key]
        self.position += 1
        return return_order


orders = {}
orders["blah"] = "thing 1"
orders["foo"] = "thing 2"
orders["bar"] = "thing 3"
orders["baz"] = "thing 4"

sales_orders = SalesOrders(orders)
for k in sales_orders:
    print(k)
