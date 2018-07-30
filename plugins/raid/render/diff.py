class Diff:
    def __init__(self, wrapped):
        self.wrapped = wrapped

    def __str__(self):
        return "```diff\n{}```".format(self.wrapped)
