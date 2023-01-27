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
    # "algos": ["MacdTA", "SMA"]
}

mux_keys = {}
for k, v in defaults.items():
    edit_key = input(
        f"{k} defaults to {v}. Enter number of values to mux, or enter to skip this key:\t\t"
    )

    if edit_key:
        value_count = int(edit_key)

        done = 1
        mux_keys[k] = []
        while done <= value_count:
            this_value = input(f"Enter value #{done} for {k}:\t\t")
            this_value_cast = do_cast(v, this_value)
            mux_keys[k].append(this_value_cast)
            done += 1

configs = []
for perm_key, perm_values in mux_keys.items():
    new_config = defaults.copy()
    for v in perm_values:

        configs.append(new_config)

# I think it is something like
# enter this key
# copy list of keys
# pop this key from list of keys
# for values in this key
#   for keys in remaining keys
#      for values in remaining keys
#          mux


"""
buy timeout intervals           1       2       3
take_profit_risk_multiplier     1.25    1.5     1.75
take_profit_pct_to_sell         0.25    0.5     0.75    1
stop_loss_trigger_pct           0.95    0.96    0.97    0.98    0.99    0.995
stop_loss_hold_intervals        0       1       2
check_sma                       True    False
sma_comparison_period           7       14      21      28      35
"""
