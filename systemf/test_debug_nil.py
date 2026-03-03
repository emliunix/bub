"""Debug Nil constructor elaboration"""
import sys
sys.path.insert(0, 'src')

from systemf.surface.parser import Lexer, Parser
from systemf.surface.pipeline import ElaborationPipeline
from systemf.surface.inference.elaborator import TypeElaborator

# Patch infer to debug constructor
original_infer = TypeElaborator.infer

def debug_infer(self, term, ctx):
    from systemf.surface.types import SurfaceConstructor
    if isinstance(term, SurfaceConstructor):
        print(f"\n=== infer(SurfaceConstructor({term.name}, args={len(term.args)})) ===")
        print(f"  args: {term.args}")
    return original_infer(self, term, ctx)

TypeElaborator.infer = debug_infer

source = '''
data List a = Nil | Cons a (List a)

treverse : ∀a. List a → List a → List a =
  Λa. λacc:List a → λxs:List a →
    case xs of
      Nil → acc
    | Cons y ys → treverse (Cons y acc) ys

reverse : ∀a. List a → List a = Λa. λxs:List a → treverse Nil xs
'''

try:
    tokens = Lexer(source).tokenize()
    decls = Parser(tokens).parse()
    pipeline = ElaborationPipeline(module_name="test")
    result = pipeline.run(decls)
    
    if result.success:
        print("✓ SUCCESS!")
    else:
        print("\n✗ FAILED:")
        for error in result.errors:
            print(f"  - {error}")
except Exception as e:
    print(f"\n✗ EXCEPTION: {e}")
