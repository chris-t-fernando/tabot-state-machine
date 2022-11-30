import json


def do_cast(target_variable, source_variable):
    try:
        if type(target_variable) == str:
            casted = str(source_variable)
        elif type(target_variable) == int:
            casted = int(source_variable)
        elif type(target_variable) == float:
            casted = float(source_variable)
        elif type(target_variable) == bool:
            casted = bool(source_variable)
        else:
            raise RuntimeError(f"Type {type(target_variable)} is unsupported for {v}")
    except ValueError as e:
        raise RuntimeError(
            f"Unable to cast {source_variable} to same type as {target_variable}"
        )
    else:
        return casted


defaults = {
    "max_play_size": 200,
    "buy_timeout_intervals": 2,
    "buy_order_type": "limit",
    "take_profit_risk_multiplier": 1.5,
    "take_profit_pct_to_sell": 0.5,
    "stop_loss_type": "market",
    "stop_loss_trigger_pct": 0.99,
    "stop_loss_hold_intervals": 1,
    "state_waiting": "MacdStateWaiting",
    "state_entering_position": "MacdStateEnteringPosition",
    "state_taking_profit": "MacdStateTakingProfit",
    "state_stopping_loss": "MacdStateStoppingLoss",
    "state_terminated": "MacdStateTerminated",
    "config_object": "MacdPlayConfig",
    "check_sma": False,
    "sma_comparison_period": 21,
}

out_list = []

while True:
    out = defaults.copy()
    out["algos"] = ["MacdTA", "SMA"]

    name = "play-"
    for k, v in defaults.items():
        parameter = input(f"Enter value for {k} (default: {v}):\t")
        if len(parameter) > 0:
            name += f"{k}={v}"
            out[k] = do_cast(v, parameter)

    out["name"] = name
    out_list.append(out)
    if input("Another combination? (default yes, n to quit):\t") == "n":
        break

# TODO this is too hard for now
# check that there aren't any duplicate plays
# set_config = set(out_list)
# if len(set_config) != out_list:
#    # there is at least one duplicate
#    print("Invalid config - found a duplicate")


# check that there aren't any duplicate names
for config in out_list:
    count = 0
    for compare_config in out_list:
        if compare_config["name"] == config["name"]:
            count += 1

    if count > 1:
        print(f"Found duplicate name: {compare_config['name']}")
