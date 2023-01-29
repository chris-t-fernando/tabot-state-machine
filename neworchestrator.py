# import __main__
from parameter_store import Ssm, S3
from core import PlayOrchestrator, StrategyHandler, RT_BACKTEST
from strategies import (
    MacdPlayConfig,
    MacdStateEnteringPosition,
    MacdStateStoppingLoss,
    MacdStateTakingProfit,
    MacdStateTerminated,
    MacdStateWaiting,
    MacdTA,
    SMA,
)

import logging

stream_handler = logging.StreamHandler()
formatter = logging.Formatter(
    "%(asctime)s - %(name)16s - %(levelname)8s - %(funcName)15s - %(message)s"
)
stream_handler.setFormatter(formatter)
root_logger = logging.getLogger()
root_logger.setLevel(logging.CRITICAL)
root_logger.addHandler(stream_handler)

level = 51
log = logging.getLogger(__name__)
log.setLevel(level)
# logging.getLogger("core.instance_state").setLevel(level)
# logging.getLogger("core.orchestrator").setLevel(level)
# logging.getLogger("strategies.macd").setLevel(level)
logging.getLogger("strategies").setLevel(level)
logging.getLogger("core").setLevel(level)

sh = StrategyHandler(globals().copy())

store = S3("mfers-tabot")
# TODO call start automatically?
po = PlayOrchestrator(store=store, strategy_handler=sh, run_type=RT_BACKTEST)
po.start()

while not po.eof:
    po.run()
    print(f"Run {str(po)} finished processing records for {po.now}")
    po.sleep()
print(f"got to end of run ID {str(po)}")
