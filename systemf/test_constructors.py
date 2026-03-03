"""Test constructor parsing in expressions"""
import sys
sys.path.insert(0, 'src')

from systemf.surface.parser import Lexer, Parser
from systemf.surface.pipeline import ElaborationPipeline

# Test 1: Nullary constructor
source1 = '''
data Maybe a = Nothing | Just a

f : Maybe Int = Nothing
'''

print("Test 1: Nullary constructor")
try:
    tokens = Lexer(source1).tokenize()
    decls = Parser(tokens).parse()
    pipeline = ElaborationPipeline(module_name="test")
    result = pipeline.run(decls)
    print("✓" if result.success else "✗", result.errors[0] if not result.success else "")
except Exception as e:
    print(f"✗ {e}")

# Test 2: Constructor with arguments
source2 = '''
data Maybe a = Nothing | Just a

f : Maybe Int = Just 42
'''

print("\nTest 2: Constructor with argument")
try:
    tokens = Lexer(source2).tokenize()
    decls = Parser(tokens).parse()
    pipeline = ElaborationPipeline(module_name="test")
    result = pipeline.run(decls)
    print("✓" if result.success else "✗", result.errors[0] if not result.success else "")
except Exception as e:
    print(f"✗ {e}")

# Test 3: Multiple constructor applications
source3 = '''
data List a = Nil | Cons a (List a)

f : List Int = Cons 1 (Cons 2 Nil)
'''

print("\nTest 3: Nested constructors")
try:
    tokens = Lexer(source3).tokenize()
    decls = Parser(tokens).parse()
    pipeline = ElaborationPipeline(module_name="test")
    result = pipeline.run(decls)
    print("✓" if result.success else "✗", result.errors[0] if not result.success else "")
except Exception as e:
    print(f"✗ {e}")

# Test 4: Constructor in function application (the failing case before)
source4 = '''
data List a = Nil | Cons a (List a)

treverse : ∀a. List a → List a → List a =
  Λa. λacc:List a → λxs:List a →
    case xs of
      Nil → acc
    | Cons y ys → treverse (Cons y acc) ys

reverse : ∀a. List a → List a = Λa. λxs:List a → treverse Nil xs
'''

print("\nTest 4: Constructor as function argument")
try:
    tokens = Lexer(source4).tokenize()
    decls = Parser(tokens).parse()
    pipeline = ElaborationPipeline(module_name="test")
    result = pipeline.run(decls)
    print("✓" if result.success else "✗", result.errors[0] if not result.success else "")
except Exception as e:
    print(f"✗ {e}")
