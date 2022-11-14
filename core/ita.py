from abc import ABC, abstractmethod
import pandas as pd


class ITA(ABC):
    @abstractmethod
    def do_ta(ohlc_data: pd.DataFrame):
        ...
