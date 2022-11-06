from core import PlayConfig


class MacdPlayConfig(PlayConfig):
    __tabot_strategy__: bool = True

    def __init__(
        self,
        buy_signal_strength: float = 1,
        check_sma: bool = True,
        sma_comparison_period: int = 20,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.buy_signal_strength = buy_signal_strength
        self.check_sma = check_sma
        self.sma_comparison_period = sma_comparison_period
