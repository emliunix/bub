"""Debug treverse Nil xs"""
import sys
sys.path.insert(0, 'src')

from systemf.surface.parser import Lexer, Parser
from systemf.surface.pipeline import ElaborationPipeline

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
        print("✗ FAILED:")
        for error in result.errors:
            print(f"  - {error}")
except Exception as e:
    print(f"✗ EXCEPTION: {e}")
