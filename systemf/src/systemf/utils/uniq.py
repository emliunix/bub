class Uniq:
    def __init__(self):
        self.uniq = 0

    def make_uniq(self) -> int:
        n = self.uniq
        self.uniq += 1
        return n

UNIQ = Uniq()
