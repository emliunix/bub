from .types import Name
from .builtins import BUILTIN_UNIQUES

from systemf.utils.uniq import Uniq


class NameCache:
    """Stable unique IDs. Same (module, name) always returns same unique."""
    uniq: Uniq

    def __init__(self, uniq: Uniq):
        self.uniq = uniq
        # (module, surface) -> Name
        self.names: dict[tuple[str, str], Name] = {}

    def get(self, module: str, name: str) -> Name:
        """Get or create a Name for the given module and surface name."""
        key = (module, name)
        if key in self.names:
            return self.names[key]

        # Check if this is a builtin with fixed unique
        if (module, name) in BUILTIN_UNIQUES:
            unique = BUILTIN_UNIQUES[(module, name)]
        else:
            unique = self.uniq.make_uniq()

        n = Name(mod=module, surface=name, unique=unique)
        self.names[key] = n
        return n
