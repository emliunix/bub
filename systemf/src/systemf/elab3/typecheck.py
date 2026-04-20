"""
typecheck module
"""

from .typecheck_expr import TypeChecker

from .types import NameGenerator, REPLContext, Name
from .types.ast import Binding, ModuleDecls, RnDataConDecl, RnDataDecl, RnTermDecl
from .types.core import CoreTm
from .types.ty import Id
from .types.tything import AnId, TypeEnv, ATyCon, ACon


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

    def typecheck(self, mod: ModuleDecls) -> tuple[TypeEnv, dict[Name, CoreTm]]:
        ty_env = self.tc_datas(mod.data_decls)
        self.type_env.update(ty_env)
        vals = self.tc_valbinds(mod.term_decls)
        ty_env.update((id.name, AnId.from_id(id)) for id, _ in vals.items())
        return ty_env, {id.name: tm for id, tm in vals.items()}

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

    def tc_valbinds(self, valbinds: list[RnTermDecl]) -> dict[Id, CoreTm]:
        items = self.typecheck_expr.bindings([Binding(b.name, b.expr) for b in valbinds], lambda xs: xs)
        return {b: tm() for b, tm in items}
