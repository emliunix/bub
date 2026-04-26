from typing import Callable, cast
from os import path

from systemf.elab3.types.protocols import Ext, REPLSessionProto, Synthesizer
from systemf.elab3.types.ty import Name, Ty, TyFun
from systemf.elab3.types.tything import AnId
from systemf.elab3.types.val import VPartial, VPrim, Val
from systemf.elab3 import builtins as bi
from systemf.elab3.val_pp import pp_val


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
    def get_primop(self, name: Name, thing: AnId, session: REPLSessionProto) -> Val | None:
        if name.surface != "test_prim":
            return None
        arg_tys, res_ty = split_fun(thing.id.ty)
        def _fun(args: list[Val]) -> Val:
            s2 = session.fork()
            print("got args:")
            for arg, arg_ty in zip(args, arg_tys):
                print(f"- {pp_val(s2, arg, arg_ty)}")
            s2.cmd_add_args(list((f"arg{i}", v, ty) for i, (ty, v) in enumerate(zip(arg_tys, args))))
            res: list[Val | None] = [None]
            s2.cmd_add_return(res, res_ty)
            s2.eval("set_return 1")
            if res[0] is None:
                raise Exception("Expected return value to be set by test_prim body")
            return res[0]
        return VPartial.create(name.surface, len(arg_tys), _fun)


def split_fun(ty: Ty) -> tuple[list[Ty], Ty]:
    def _go(ty: Ty):
        match ty:
            case TyFun(arg, res):
                yield arg
                yield from _go(res)
            case _:
                yield ty
    tys = list(_go(ty))
    return tys[:-1], tys[-1]
