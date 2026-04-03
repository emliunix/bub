"""
typecheck module
"""

from systemf.src.systemf.elab3.types import NameGenerator, REPLContext, Name
from systemf.src.systemf.elab3.types.ast import ModuleDecls, RnDataDecl
from systemf.src.systemf.elab3.types.core import CoreTm
from systemf.src.systemf.elab3.types.tything import TypeEnv, ATyCon, ACon


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
        return TypecheckExpr(self.ctx, self.name_gen, self.type_env)

    def typecheck(self, mod: ModuleDecls) -> tuple[TypeEnv, dict[Name, CoreTm]]:
        self.tc_datas(mod.data_decls)
        self.tc_funs
        pass

    def tc_datas(self, data_decls: list[RnDataDecl]):
        """
        Simply populate type env with data types.
        """
        for data_decl in data_decls:
            self.type_env[data_decl.name] = ATyCon(data_decl.name, data_decl.params, data_decl.constructors)
            for tag, con in enumerate(data_decl.constructors):
                self.type_env[con.name] = ACon(con.name, tag, len(con.args), con.args, data_decl.name)

    def resolve_type(self, name: Name):
        """
        Resolve and cache a tything lookup, local first, then global modules
        """
        # first try local type_env
        if name in self.type_env:
            return self.type_env[name]
        else:
            # fallback to locate module and then fetch from there
            m = self.ctx.load(name.mod)
            if m is not None:
                return m.type_env.get(name)
            else:
                raise Exception(f"Cannot resolve type {name}, module {name.mod} not found")
    