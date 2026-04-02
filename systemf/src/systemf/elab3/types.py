from typing import Protocol

from systemf.utils.uniq import Uniq


class REPLContext(Protocol):
    uniq: Uniq

    def load_module(self, name: str) -> Module: ...
