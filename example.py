from strategy_macd import (
    MacdStateEnteringPosition,
    MacdStateStoppingLoss,
    MacdStateTakingProfit,
    MacdStateWaiting,
    MacdStateTerminated,
)
from abstracts import APlayTemplate, APlayConfig, APlayController, Symbol
import logging

logger = logging.getLogger()
stream_handler = logging.StreamHandler()
formatter = logging.Formatter(
    "%(asctime)s - %(name)16s - %(levelname)8s - %(funcName)15s - %(message)s"
)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)
logger.setLevel(logging.CRITICAL)

logging.getLogger(__name__).setLevel(logging.DEBUG)
logging.getLogger("symbol_data").setLevel(logging.DEBUG)
logging.getLogger("strategy_machine").setLevel(logging.DEBUG)
logging.getLogger("strategy_macd").setLevel(logging.DEBUG)

# config = MacdPlayConfig()
# machine = MacdPlayInstance(config)
# machine.run()
# machine.run()
# machine.run()
# machine.run()
# machine.run()
# machine.run()

play_template_1 = APlayTemplate(
    buy_signal_strength=1,
    take_profit_trigger_pct_of_risk=1,
    take_profit_pct_to_sell=1,
    stop_loss_type="market",
    stop_loss_trigger_pct=0.99,
    stop_loss_hold_intervals=1,
)

play_template_2 = APlayTemplate(
    buy_signal_strength=0.9,
    take_profit_trigger_pct_of_risk=0.9,
    take_profit_pct_to_sell=0.9,
    stop_loss_type="limit",
    stop_loss_trigger_pct=0.90,
    stop_loss_hold_intervals=0.9,
)


play_config = APlayConfig(
    state_waiting=MacdStateWaiting,
    state_entering_position=MacdStateEnteringPosition,
    state_taking_profit=MacdStateTakingProfit,
    state_stopping_loss=MacdStateStoppingLoss,
    state_terminated=MacdStateTerminated,
    buy_budget=200,
    play_templates=[play_template_1, play_template_2],
)


symbol = Symbol(
    yf_symbol="BTC-USD", alp_symbol="BTCUSD"
)  # need to do api calls to generate increments etc


controller = APlayController(symbol, play_config)  # also creates a play telemetry object
controller.start_play()
controller.run()
controller.run()
controller.run()
controller.run()
controller.run()
