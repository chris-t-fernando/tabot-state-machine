from core import ITA
import pandas as pd
import btalib


class SMA(ITA):
    __tabot_strategy__: bool = True

    class SMAColumns:
        df: pd.DataFrame

        def __init__(self, df: pd.DataFrame) -> None:
            self.df = df

    def do_ta(ohlc_data: pd.DataFrame):
        btadf = btalib.sma(ohlc_data).df
        return SMA.SMAColumns(btadf)
