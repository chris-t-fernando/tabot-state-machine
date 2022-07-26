def banana(**kwargs):
    for a in kwargs:
        print(a, kwargs[a])


banana(kwargs={"z": 1, "y": 2})
