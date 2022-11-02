import __main__
from broker_api import AlpacaAPI, BackTestAPI, ITradeAPI
from parameter_store import Ssm
from core import PlayOrchestrator

# from strategies.macd import MacdPlayConfig
import logging

stream_handler = logging.StreamHandler()
formatter = logging.Formatter(
    "%(asctime)s - %(name)16s - %(levelname)8s - %(funcName)15s - %(message)s"
)
stream_handler.setFormatter(formatter)
root_logger = logging.getLogger()
root_logger.setLevel(logging.CRITICAL)
root_logger.addHandler(stream_handler)

level = 9
log = logging.getLogger(__name__)
log.setLevel(level)
logging.getLogger("core.instance_state").setLevel(level)
logging.getLogger("core.orchestrator").setLevel(level)
logging.getLogger("strategies.macd").setLevel(level)


store = Ssm()
po = PlayOrchestrator(store)
po.start()


#    def _enumerate_symbols(self):
#        for cat in self.symbol_categories:
#            new_symbols = set(
#                json.loads(self.store.get(f"{self._store_path}/{cat}/symbols"))
#            )
#            if len(new_symbols & self.uninstantiated_symbols) > 0:
#                log.warning(
#                    f"Symbol appears in more than one category: {new_symbols&self.uninstantiated_symbols}"
#                )
#            self.uninstantiated_symbols |= new_symbols
