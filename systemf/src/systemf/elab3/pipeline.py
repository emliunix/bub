from systemf.elab3.types import Module, REPLContext

from systemf.surface.parser import parse_program


class Pipeline:
    ctx: REPLContext
    mod_name: str
    file_path: str
    code: str


    def __init__(self, ctx: REPLContext, mod_name: str, file_path: str, code: str):
        self.ctx = ctx
        self.mod_name = mod_name
        self.file_path = file_path
        self.code = code


    def execute(self) -> Module:
        parse_program(self.code, self.file_path)

        # 1. Parse
        reader = Reader(self.ctx.reader_env)
        ast = reader.read(code)

        # 2. Rename
        rename = Rename(self.ctx, self.ctx.reader_env, self.mod_name)
        rename_result = rename.rename(ast)

        # 3. Typecheck
        typecheck = Typecheck(self.mod_name, self.ctx, rename.name_gen)
        ty_env, vals = typecheck.typecheck(rename_result)

        return Module(
            name=self.mod_name,
            items=ty_env,
            vals=vals,
            exports=list(ty_env.keys()),
            source_path=self.file_path
        )


def execute(ctx: REPLContext, mod_name: str, file_path: str, code: str) -> Module:
    return Pipeline(ctx, mod_name, file_path, code).execute()
