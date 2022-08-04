from tabnanny import check
from core.abstracts import (
    IStateWaiting,
    IStateEnteringPosition,
    State,
    IStateStoppingLoss,
    IStateTakingProfit,
    IStateTerminated,
    Instance,
    InstanceTemplate,
)

import btalib
import pandas as pd
from dateutil.relativedelta import relativedelta
from numpy import NaN
import numpy as np
import logging
from time import sleep


log = logging.getLogger(__name__)


class MacdTA:
    class MacdColumns:
        df: pd.DataFrame

        def __init__(self, df: pd.DataFrame) -> None:
            self.df = df

    def get_interval_settings(interval):
        minutes_intervals = ["1m", "2m", "5m", "15m", "30m", "60m", "90m"]
        max_period = {"1m": 6, "2m": 59, "5m": 59, "15m": 59, "30m": 59, "60m": 500, "90m": 59}

        if interval in minutes_intervals:
            return (
                relativedelta(minutes=int(interval[:-1])),
                relativedelta(days=max_period[interval]),
            )
        else:
            raise ValueError(f"Interval {interval} is not implemented")

    def macd(ohlc_data, interval="5m"):
        btadf = btalib.macd(ohlc_data).df

        # change names to avoid collision
        df = btadf.rename(
            columns={
                "macd": "macd_macd",
                "signal": "macd_signal",
                "histogram": "macd_histogram",
            }
        )

        df = df.assign(
            macd_crossover=False,
            # macd_signal_crossover=False,
            macd_above_signal=False,
            macd_cycle="red",
        )

        # signal here means MA26
        # macd here means MA12
        # so macd_above_signal means MA12 above MA26
        df["macd_above_signal"] = np.where(df["macd_macd"] > df["macd_signal"], True, False)
        # blue means MA12 is above MA26
        df["macd_cycle"] = np.where(df["macd_macd"] > df["macd_signal"], "blue", "red")
        # crossover happens when MA12 crosses over MA26
        df["macd_crossover"] = df.macd_above_signal.ne(df.macd_above_signal.shift())

        return MacdTA.MacdColumns(df)


class MacdInstanceTemplate(InstanceTemplate):
    def __init__(
        self,
        buy_signal_strength: float,
        take_profit_trigger_pct_of_risk: float,
        take_profit_pct_to_sell: float,
        stop_loss_trigger_pct: float,
        stop_loss_type: str = "market",
        stop_loss_hold_intervals: int = 1,
        buy_timeout_intervals: int = 2,
        check_sma: bool = True,
    ) -> None:
        super().__init__(
            buy_signal_strength=buy_signal_strength,
            take_profit_trigger_pct_of_risk=take_profit_trigger_pct_of_risk,
            take_profit_pct_to_sell=take_profit_pct_to_sell,
            stop_loss_trigger_pct=stop_loss_trigger_pct,
            stop_loss_type=stop_loss_type,
            stop_loss_hold_intervals=stop_loss_hold_intervals,
            buy_timeout_intervals=buy_timeout_intervals,
        )
        self.check_sma = check_sma


class MacdStateWaiting(IStateWaiting):
    def __init__(self, parent_instance: Instance, previous_state: State = None) -> None:
        super().__init__(parent_instance=parent_instance, previous_state=previous_state)

    def check_exit(self):
        df = self.ohlc.get_range()
        row = df.iloc[-1]

        crossover = MacdStateWaiting.check_crossover(row)
        macd_negative = MacdStateWaiting.check_macd_negative(row)
        last_sma = MacdStateWaiting.get_last_sma(df=df)
        recent_average_sma = MacdStateWaiting.get_recent_average_sma(df=df)
        sma_trending_up = MacdStateWaiting.check_sma(
            last_sma=last_sma, recent_average_sma=recent_average_sma
        )

        signal_found = crossover and macd_negative
        if self.config.check_sma:
            signal_found = sma_trending_up and signal_found

        if signal_found:
            # all conditions met for a buy
            log.info(
                f"{self.symbol_str}: FOUND BUY SIGNAL AT {row.name} (MACD {round(row.macd_macd,4)} vs "
                f"signal {round(row.macd_signal,4)}, SMA LAST {round(last_sma,4)} vs AVG {round(recent_average_sma,4)})"
            )
            return State.STATE_MOVE, MacdStateEnteringPosition, {}

        log.log(
            9,
            f"{self.symbol_str}: No buy signal at {df.index[-1]} (MACD {round(row.macd_macd,4)} vs signal "
            f"{round(row.macd_signal,4)}, SMA {round(last_sma,4)} vs {round(recent_average_sma,4)}",
        )
        return State.STATE_STAY, None, {}

    def do_exit(self):
        log.log(9, f"doing exit on {self}")
        return

    def get_last_sma(df):
        return df.iloc[-1].sma

    def get_recent_average_sma(df):
        return df.sma.iloc[-20]

    def check_macd_negative(row):
        if row.macd_macd < 0:
            macd_negative = True
            log.log(9, f"MACD is less than 0: {row.macd_macd}")
            return True
        else:
            log.log(9, "MACD is not negative")
            return False

    def check_crossover(row):
        if row.macd_crossover == True:
            log.log(9, f"MACD crossover found")
            return True
        else:
            log.log(9, f"MACD crossover was not found")
            return False

    def check_sma(last_sma: float, recent_average_sma: float, ignore_sma: bool = False):
        if ignore_sma:
            log.warning(f"Returning True since ignore_sma is enabled")
            return True

        if last_sma > recent_average_sma:
            log.log(9, f"True, last SMA {last_sma} > {recent_average_sma}")
            return True
        else:
            log.log(9, f"False, last SMA {last_sma} > {recent_average_sma}")
            return False


class MacdStateEnteringPosition(IStateEnteringPosition):
    def __init__(self, previous_state: State, parent_instance: Instance = None) -> None:
        super().__init__(parent_instance=parent_instance, previous_state=previous_state)

    def check_exit(self):
        log.log(9, f"checking exit on {self}")
        return State.STATE_MOVE, MacdStateTakingProfit, {}

    def do_exit(self):
        log.log(9, f"doing exit on {self}")
        return


class MacdStateTakingProfit(IStateTakingProfit):
    def __init__(self, previous_state: State, parent_instance: Instance = None) -> None:
        super().__init__(parent_instance=parent_instance, previous_state=previous_state)

    def check_exit(self):
        log.log(9, f"checking exit on {self}")
        return State.STATE_MOVE, MacdStateStoppingLoss, {}

    def do_exit(self):
        log.log(9, f"doing exit on {self}")
        return


class MacdStateStoppingLoss(IStateStoppingLoss):
    def __init__(self, previous_state: State, parent_instance: Instance = None) -> None:
        super().__init__(parent_instance=parent_instance, previous_state=previous_state)

    def check_exit(self):
        log.log(9, f"checking exit on {self}")
        return State.STATE_MOVE, MacdStateTerminated, {}

    def do_exit(self):
        log.log(9, f"doing exit on {self}")
        return


class MacdStateTerminated(IStateTerminated):
    def __init__(self, previous_state: State, parent_instance: Instance = None) -> None:
        super().__init__(parent_instance=parent_instance, previous_state=previous_state)

    def check_exit(self):
        log.log(9, f"checking exit on {self}")
        return State.STATE_STAY, None, {}

    def do_exit(self):
        raise NotImplementedError(f"Terminated state cannot implement do_exit()")
