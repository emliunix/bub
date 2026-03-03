"""Debug Nil constructor elaboration"""
import sys
sys.path.insert(0, 'src')

from systemf.surface.parser import Lexer, Parser
from systemf.surface.pipeline import ElaborationPipeline

source = '''
data List a = Nil | Cons a (List a)

f : ∀a. List a → List a = Λa. λxs:List a → Nil
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
