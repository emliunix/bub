from typing import Callable, cast
from os import path

from systemf.elab3.types.protocols import Ext, REPLSessionProto, Synthesizer
from systemf.elab3.types.ty import Name, Ty
from systemf.elab3.types.tything import AnId
from systemf.elab3.types.val import VPrim, Val
from systemf.elab3 import builtins as bi


class BubExt(Ext):
    @property
    def name(self) -> str:
        return "bub"
    
    def search_paths(self) -> list[str]:
        return [path.basename(__file__)]
    
    def synthesizer(self) -> dict[str, Synthesizer] | None:
        return {
            "bub": PrimOps(),
        }

class PrimOps(Synthesizer):
    def get_primop(self, name: Name, thing: AnId, session: REPLSessionProto) -> Callable[[list[Val]], Val] | None:
        return None