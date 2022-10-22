from core import (
    StateWaiting,
    StateEnteringPosition,
    State,
    StateStoppingLoss,
    StateTakingProfit,
    StateTerminated,
    Instance,
    InstanceTemplate,
)

import btalib
import pandas as pd
from dateutil.relativedelta import relativedelta
from numpy import NaN
import numpy as np
import logging


log = logging.getLogger(__name__)


class MacdTA:
    class MacdColumns:
        df: pd.DataFrame

        def __init__(self, df: pd.DataFrame) -> None:
            self.df = df

    def get_interval_settings(interval):
        minutes_intervals = ["1m", "2m", "5m", "15m", "30m", "60m", "90m"]
        max_period = {
            "1m": 6,
            "2m": 59,
            "5m": 59,
            "15m": 59,
            "30m": 59,
            "60m": 500,
            "90m": 59,
        }

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
        df["macd_above_signal"] = np.where(
            df["macd_macd"] > df["macd_signal"], True, False
        )
        # blue means MA12 is above MA26
        df["macd_cycle"] = np.where(df["macd_macd"] > df["macd_signal"], "blue", "red")
        # crossover happens when MA12 crosses over MA26
        df["macd_crossover"] = df.macd_above_signal.ne(df.macd_above_signal.shift())

        return MacdTA.MacdColumns(df)


class MacdInstanceTemplate(InstanceTemplate):
    def __init__(
        self,
        name: str,
        buy_signal_strength: float,
        take_profit_risk_multiplier: float,
        take_profit_pct_to_sell: float,
        stop_loss_trigger_pct: float,
        stop_loss_type: str = "market",
        stop_loss_hold_intervals: int = 1,
        buy_order_type: str = "limit",
        buy_timeout_intervals: int = 2,
        check_sma: bool = True,
        sma_comparison_period: int = 20,
    ) -> None:
        super().__init__(
            name=name,
            buy_signal_strength=buy_signal_strength,
            buy_order_type=buy_order_type,
            take_profit_risk_multiplier=take_profit_risk_multiplier,
            take_profit_pct_to_sell=take_profit_pct_to_sell,
            stop_loss_trigger_pct=stop_loss_trigger_pct,
            stop_loss_type=stop_loss_type,
            stop_loss_hold_intervals=stop_loss_hold_intervals,
            buy_timeout_intervals=buy_timeout_intervals,
        )
        self.check_sma = check_sma
        self.sma_comparison_period = sma_comparison_period


class MacdStateWaiting(StateWaiting):
    def __init__(self, parent_instance: Instance, previous_state: State = None) -> None:
        super().__init__(parent_instance=parent_instance, previous_state=previous_state)

    def check_exit(self):
        self.log.debug(f"{self.symbol_str}: Running check_exit()")
        config_period = self.config.sma_comparison_period

        df = self.ohlc.get_range()
        row = df.iloc[-1]

        crossover = MacdStateWaiting.check_crossover(row)
        macd_negative = MacdStateWaiting.check_macd_negative(row)
        last_sma = MacdStateWaiting.get_last_sma(df=df)
        recent_average_sma = MacdStateWaiting.get_recent_average_sma(
            df=df, period=config_period
        )
        sma_trending_up = MacdStateWaiting.check_sma(
            last_sma=last_sma, recent_average_sma=recent_average_sma
        )

        signal_found = crossover and macd_negative
        if self.config.check_sma:
            signal_found = sma_trending_up and signal_found

        if signal_found:
            # all conditions met for a buy
            self.log.info(
                f"{self.symbol_str}: FOUND BUY SIGNAL AT {row.name} (MACD {round(row.macd_macd,4)} vs "
                f"signal {round(row.macd_signal,4)}, SMA LAST {round(last_sma,4)} vs AVG {round(recent_average_sma,4)})"
            )
            return State.STATE_MOVE, MacdStateEnteringPosition, {}

        self.log.log(
            9,
            f"{self.symbol_str}: No buy signal at {df.index[-1]} (MACD {round(row.macd_macd,4)} vs signal "
            f"{round(row.macd_signal,4)}, SMA {round(last_sma,4)} vs {round(recent_average_sma,4)}",
        )
        return State.STATE_STAY, None, {}

    def do_exit(self):
        # TODO - change signature on base class to the variables that must be handed to next step?

        # calculate stop loss
        df = self.ohlc.get_range()

        blue_cycle_start = MacdStateWaiting.get_blue_cycle_start(df=df)
        red_cycle_start = MacdStateWaiting.get_red_cycle_start(
            df=df, before_date=blue_cycle_start
        )

        stop_loss_unit = MacdStateWaiting.calculate_stop_loss_unit_price(
            df=df,
            start_date=red_cycle_start,
            end_date=blue_cycle_start,
        )

        stop_unit_date = MacdStateWaiting.calculate_stop_loss_date(
            df=df,
            start_date=red_cycle_start,
            end_date=blue_cycle_start,
        )

        intervals_since_stop = MacdStateWaiting.count_intervals(
            df=df, start_date=stop_unit_date
        )

        self.log.log(
            logging.DEBUG,
            f"{self.symbol}: Last cycle started on {red_cycle_start}, "
            f"{intervals_since_stop} intervals ago",
        )
        self.log.log(
            logging.DEBUG,
            f"{self.symbol}: The lowest price during that cycle was {stop_loss_unit} "
            f"on {stop_unit_date}. This will be used as the stop loss for this instance",
        )

        # put stop loss in to instance
        self.parent_instance.stop_loss_price = stop_loss_unit

        super().do_exit()

    def calculate_stop_loss_unit_price(df: pd.DataFrame, start_date, end_date):
        return df.loc[start_date:end_date].Close.min()

    def calculate_stop_loss_date(df: pd.DataFrame, start_date, end_date):
        return df.loc[start_date:end_date].Close.idxmin()

    def count_intervals(df: pd.DataFrame, start_date, end_date=None):
        if end_date == None:
            return len(df.loc[start_date:])
        else:
            return len(df.loc[start_date:end_date])

    def get_last_sma(df: pd.DataFrame):
        return df.iloc[-1].sma

    def get_recent_average_sma(df: pd.DataFrame, period: int):
        return df.sma.iloc[-period]

    def check_macd_negative(row):
        macd_negative = row.macd_macd < 0
        log.log(9, f"MACD {row.macd_macd} is < 0 = {macd_negative}")
        return macd_negative

    def check_crossover(row: pd.Series):
        crossover = row.macd_crossover == True
        log.log(9, f"MACD crossover = {crossover}")
        return crossover

    def check_sma(last_sma: float, recent_average_sma: float, ignore_sma: bool = False):
        if ignore_sma:
            log.warning(f"SMA check = True (ignore_sma is enabled)")
            return True

        sma_rising = last_sma > recent_average_sma
        log.log(9, f"SMA check = {sma_rising} ({last_sma} > {recent_average_sma})")
        return sma_rising

    # maybe dont need these. need to store this stuff in instance, not state
    def get_red_cycle_start(df: pd.DataFrame, before_date: pd.Timestamp):
        return df.loc[
            (df["macd_cycle"] == "blue")
            & (df.index < before_date)
            & (df.macd_crossover == True)
        ].index[-1]

    def get_blue_cycle_start(df: pd.DataFrame):
        return df.loc[(df.macd_crossover == True) & (df.macd_macd < 0)].index[-1]


class MacdStateEnteringPosition(StateEnteringPosition):
    def __init__(self, previous_state: State, parent_instance: Instance = None) -> None:
        super().__init__(parent_instance=parent_instance, previous_state=previous_state)

    def check_exit(self):
        log.log(9, f"checking exit on {self}")
        return super().check_exit()

    def do_exit(self):
        log.log(9, f"doing exit on {self}")
        return super().do_exit()


class MacdStateTakingProfit(StateTakingProfit):
    def __init__(self, previous_state: State, parent_instance: Instance = None) -> None:
        # if you're going to override the take profit units or price, do it before calling super init
        super().__init__(parent_instance=parent_instance, previous_state=previous_state)

    def check_exit(self):
        log.log(9, f"checking exit on {self}")
        return super().check_exit()

    # def do_exit(self):
    #    log.log(9, f"doing exit on {self}")
    #    return super().do_exit()


class MacdStateStoppingLoss(StateStoppingLoss):
    def __init__(self, previous_state: State, parent_instance: Instance = None) -> None:
        super().__init__(parent_instance=parent_instance, previous_state=previous_state)

    def check_exit(self):
        log.log(9, f"checking exit on {self}")
        return super().check_exit()


class MacdStateTerminated(StateTerminated):
    def __init__(self, previous_state: State, parent_instance: Instance = None) -> None:
        super().__init__(parent_instance=parent_instance, previous_state=previous_state)

    def check_exit(self):
        log.log(9, f"checking exit on {self}")
        return State.STATE_STAY, None, {}

    def do_exit(self):
        raise NotImplementedError(f"Terminated state cannot implement do_exit()")
