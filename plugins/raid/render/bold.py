class Bold:
    def __init__(self, wrapped):
        self.wrapped = wrapped

    def __str__(self):
        return "**{}**".format(self.wrapped)
