"""
typecheck module
"""

from systemf.elab3.types.tc import NonRecGroup, RecGroup
from .typecheck_expr import TypeChecker, ds_binding

from .types import NameGenerator, REPLContext, Name, Ty
from .types.ast import Binding, ModuleDecls, RnDataConDecl, RnDataDecl, RnPrimOpDecl, RnPrimTyDecl, RnTermDecl
from .types.core import CoreTm, CoreLet, Rec, C
from .types.ty import Id
from .types.tything import APrimTy, AnId, TypeEnv, ATyCon, ACon
from systemf.elab3.types import core


class Typecheck:
    mod_name: str
    ctx: REPLContext
    name_gen: NameGenerator
    type_env: TypeEnv


    def __init__(self, mod_name: str, ctx: REPLContext, name_gen: NameGenerator):
        self.mod_name = mod_name
        self.ctx = ctx
        self.name_gen = name_gen
        self.type_env = {}
    
    @property
    def typecheck_expr(self):
        return TypeChecker(
            self.ctx,
            self.mod_name,
            self.name_gen,
            self.type_env
        )

    def typecheck(self, mod: ModuleDecls) -> tuple[TypeEnv, dict[Name, core.Binding]]:
        ty_env = self.tc_datas(mod.data_decls)
        ty_env.update(self.tc_prims(mod.prim_ty_decls, mod.prim_op_decls))

        # update for tc_valbinds
        self.type_env.update(ty_env)
        bindings = self.tc_valbinds(mod.term_decls)

        ty_env.update((id.name, AnId.from_id(id)) for id, _ in bindings)
        return ty_env, {n.name: tm for n, tm in bindings}

    def tc_datas(self, data_decls: list[RnDataDecl]) -> TypeEnv:
        """
        Simply populate type env with data types.
        """

        env: TypeEnv = {}

        def _acon(tag: int, con: RnDataConDecl) -> ACon:
            return ACon(con.name, tag, len(con.fields), con.fields, con.tycon.name)
        for data_decl in data_decls:
            cons = [_acon(i, con) for i, con in enumerate(data_decl.constructors)]
            env[data_decl.name] = ATyCon(data_decl.name, data_decl.tyvars, cons)
            for con in cons:
                env[con.name] = con
        return env

    def tc_prims(self, ptys: list[RnPrimTyDecl], pops: list[RnPrimOpDecl]) -> TypeEnv:
        env: TypeEnv = {}
        for pty in ptys:
            env[pty.name] = APrimTy(pty.name, pty.tyvars)
        for pop in pops:
            name, ty = pop.name.name, pop.name.type_ann
            env[name] = AnId(name, Id(name, ty), is_prim=True)
        return env

    def tc_valbinds(self, valbinds: list[RnTermDecl]) -> list[tuple[Id, core.Binding]]:
        groups, _ = self.typecheck_expr.bindings([Binding(b.name, b.expr) for b in valbinds], lambda: None)
        result = {}
        bs = [
            ds_binding(group)
            for group in groups
        ]

        def _ids(b: core.Binding) -> list[Id]:
            match b:
                case core.NonRec(id, _):
                    return [id]
                case core.Rec(bindings):
                    return [id for id, _ in bindings]
                case _: raise Exception("unreachable")
        res = []
        for b in bs:
            for n in _ids(b):
                if n in res:
                    raise Exception(f"duplicate binding for {n}")
                # FIX: the sharing of RecGroup
                res.append((n, b))
        return res
