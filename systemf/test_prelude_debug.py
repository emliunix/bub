"""Debug prelude loading"""
import sys
sys.path.insert(0, 'src')

from systemf.surface.parser import Lexer, Parser
from systemf.surface.pipeline import ElaborationPipeline

with open('prelude.sf', 'r') as f:
    source = f.read()

try:
    tokens = Lexer(source).tokenize()
    decls = Parser(tokens).parse()
    print(f"Parsed {len(decls)} declarations")
    
    pipeline = ElaborationPipeline(module_name="Prelude")
    result = pipeline.run(decls)
    
    if result.success:
        print("✓ SUCCESS!")
    else:
        print("✗ FAILED:")
        for error in result.errors:
            print(f"  - {error}")
except Exception as e:
    import traceback
    traceback.print_exc()
