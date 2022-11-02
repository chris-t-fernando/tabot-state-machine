class InstanceList:
    instances: list

    def __init__(self) -> None:
        self.instances = []

    def append(self, new_instance):
        self.instances.append(new_instance)

    @property
    def total_gain(self):
        gain = 0
        for i in self.instances:
            gain += i.total_gain
        return gain
