class EvalOutput:
    pass

class REPL:
    def eval(self, input: str) -> EvalOutput:
        m = self.mk_repl_mod()
        ast = self.parse(input)
        self.elab_with_mod(m, ast)
        return EvalOutput()

    def elab_with_mod(self, m, ast):
        env_reader = self.mk_elab_env_reader(m)
        elaborate(m, env_reader, ast)
        # imports = get_import_specs(ast)
        # self.add_imports(m, imports)
        # decls = get_decls(ast)
        # self.elab_decls(m, decls)
        # valbinds = get_valbinds(ast)
        # self.elab_valbinds(m, env_reader, valbinds)
