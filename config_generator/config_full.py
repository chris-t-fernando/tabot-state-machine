from parameter_store import S3
import json
import itertools
import uuid


def generate_name(length: int = 6):
    return "conf" + uuid.uuid4().hex[:length].upper()


s3_handle = S3("mfers-tabot")

defaults = {
    "max_play_size": 200,
    "buy_order_type": "limit",
    "stop_loss_type": "market",
    "state_waiting": "MacdStateWaiting",
    "state_entering_position": "MacdStateEnteringPosition",
    "state_taking_profit": "MacdStateTakingProfit",
    "state_stopping_loss": "MacdStateStoppingLoss",
    "state_terminated": "MacdStateTerminated",
    "config_object": "MacdPlayConfig",
    "algos": ["MacdTA", "SMA"],
    "sma_comparison_period": 28,
}
generated_configs = []

config_parameters = {
    "buy_timeout_intervals": [2],
    "take_profit_risk_multiplier": [1.5, 1.75],
    "take_profit_pct_to_sell": [0.5, 0.75, 1],
    "stop_loss_trigger_pct": [0.95, 0.97, 0.99],
    "stop_loss_hold_intervals": [0, 1, 2],
    "check_sma": [True, False],
}

# config_parameters = {
#    "take_profit_risk_multiplier": [1.5],
#    "stop_loss_trigger_pct": [0.99],
#    "check_sma": [True],
#    "buy_timeout_intervals": [2],
#    "stop_loss_hold_intervals": [1],
#    "take_profit_pct_to_sell": [0.5],
# }

config_parameters = {
    "buy_timeout_intervals": [2],
    "take_profit_risk_multiplier": [1.5, 1.75],
    "take_profit_pct_to_sell": [0.5, 0.75, 1],
    "stop_loss_trigger_pct": [0.95, 0.97, 0.99],
    "stop_loss_hold_intervals": [0, 1],
    "check_sma": [True],
}


# grab all the lists of different config values we want to generate
config_values = []
for this_value in config_parameters.values():
    config_values.append(this_value)

# calculate the product of all of these permutations
value_product = list(itertools.product(*config_values))

# now reconstruct the product values back to their keys, and then add the default config values to them to create a fully formed config
keys = list(config_parameters.keys())
for this_perm in value_product:
    # dict comprehension to join key=>value from the two list objects
    res = {keys[i]: this_perm[i] for i in range(len(keys))}

    # combine default values with this permutation
    this_row = defaults | res
    this_row["name"] = generate_name()
    generated_configs.append(this_row)

zz = s3_handle.put(
    "/tabot/play_library/paper/crypto_alt/sideways", json.dumps(generated_configs)
)
zz = s3_handle.put(
    "/tabot/play_library/paper/crypto_stable/sideways", json.dumps(generated_configs)
)
zz = s3_handle.put(
    "/tabot/play_library/paper/crypto_alt/bear", json.dumps(generated_configs)
)
zz = s3_handle.put(
    "/tabot/play_library/paper/crypto_stable/bear", json.dumps(generated_configs)
)
zz = s3_handle.put(
    "/tabot/play_library/paper/crypto_alt/bull", json.dumps(generated_configs)
)
zz = s3_handle.put(
    "/tabot/play_library/paper/crypto_stable/bull", json.dumps(generated_configs)
)
zz = s3_handle.put(
    "/tabot/play_library/paper/crypto_alt/choppy", json.dumps(generated_configs)
)
zz = s3_handle.put(
    "/tabot/play_library/paper/crypto_stable/choppy", json.dumps(generated_configs)
)

s3_handle.put(
    "/tabot/play_library/paper/symbol_categories",
    json.dumps(["crypto_stable", "crypto_alt"]),
)
s3_handle.put(
    "/tabot/play_library/paper/market_conditions",
    json.dumps(["bull", "sideways", "choppy", "bear"]),
)
s3_handle.put(
    "/tabot/play_library/paper/crypto_alt/symbols",
    json.dumps(["SOL-USD"]),
)
s3_handle.put(
    "/tabot/play_library/paper/crypto_stable/symbols",
    json.dumps(["XRP-USD"]),
)

print("bana")
