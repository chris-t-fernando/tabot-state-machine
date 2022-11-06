class StrategyHandler:
    strategy_objects: dict

    def __init__(self, global_variables: dict):
        strategy_objects = {}
        for g in global_variables:
            if hasattr(global_variables[g], "__tabot_strategy__"):
                strategy_objects[g] = global_variables[g]
        self.strategy_objects = strategy_objects

    def __iter__(self):
        return iter(self.strategy_objects)

    def __next__(self):
        next(self.strategy_objects)

    def __contains__(self, strategy):
        for s in self.strategy_objects.keys():
            if strategy == s:
                return True

        return False

    def __getitem__(self, item):
        return self.strategy_objects[item]
