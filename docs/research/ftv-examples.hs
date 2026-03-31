-- Test cases for ftv(ρ) - ftv(Γ) calculation
-- Demonstrating when generalization happens vs doesn't

module Main where

import Data.List ((\\))

-- Simplified: represent metas as strings, env as list of types
type Meta = String
type Type = [Meta]  -- Just list of free metas for simplicity

-- | Calculate ftv(ρ) - ftv(Γ)
candidatesForGeneralization :: Type -> [Type] -> [Meta]
candidatesForGeneralization rho gamma = 
    let ftv_rho = rho                    -- metas in result
        ftv_gamma = concat gamma         -- metas locked in environment
    in ftv_rho \\ ftv_gamma              -- set difference

-- Test 1: Top-level let - should generalize
-- let id = \x -> x
-- ρ = ["_a", "_a"] (represents _a → _a)
-- Γ = [] (empty at top level)
test1 :: IO ()
test1 = do
    let rho = ["_a", "_a"]              -- _a → _a
        gamma = []                       -- empty env
        candidates = candidatesForGeneralization rho gamma
    putStrLn $ "Test 1: let id = \\x -> x"
    putStrLn $ "  ρ = " ++ show rho ++ " (_a → _a)"
    putStrLn $ "  Γ = " ++ show (gamma :: [[String]])
    putStrLn $ "  ftv(ρ) = " ++ show rho
    putStrLn $ "  ftv(Γ) = []"
    putStrLn $ "  ftv(ρ) - ftv(Γ) = " ++ show candidates
    putStrLn $ "  Result: id : ∀a. a → a (generalized!)"
    putStrLn ""

-- Test 2: Lambda body - should NOT generalize  
-- \x -> (let y = x in y)
-- After inferring body, ρ = ["_a"] (y's type is _a)
-- Γ = [["_a"]] (x : _a in environment)
test2 :: IO ()
test2 = do
    let rho = ["_a"]                    -- y has type _a
        gamma = [["_a"]]                 -- x : _a in env
        candidates = candidatesForGeneralization rho gamma
    putStrLn $ "Test 2: \\x -> (let y = x in y)"
    putStrLn $ "  ρ = " ++ show rho ++ " (y's type)"
    putStrLn $ "  Γ = " ++ show (gamma :: [[String]]) ++ " (x : _a)"
    putStrLn $ "  ftv(ρ) = " ++ show rho
    putStrLn $ "  ftv(Γ) = [\"_a\"]"
    putStrLn $ "  ftv(ρ) - ftv(Γ) = " ++ show candidates
    putStrLn $ "  Result: y : _a (monomorphic, NOT ∀a.a)"
    putStrLn ""

-- Test 3: Multiple free variables - generalize subset
-- let pair = \x y -> (x, y)
-- After inference: ρ = ["_a", "_b"] (_a → _b → (_a, _b))
-- Γ = [] (empty at top level)
test3 :: IO ()
test3 = do
    let rho = ["_a", "_b"]              -- _a → _b → Pair _a _b
        gamma = []
        candidates = candidatesForGeneralization rho gamma
    putStrLn $ "Test 3: let pair = \\x y -> (x, y)"
    putStrLn $ "  ρ = " ++ show rho ++ " (_a → _b → Pair _a _b)"
    putStrLn $ "  Γ = " ++ show (gamma :: [[String]])
    putStrLn $ "  ftv(ρ) - ftv(Γ) = " ++ show candidates
    putStrLn $ "  Result: pair : ∀a b. a → b → (a, b)"
    putStrLn ""

-- Test 4: Partially constrained
-- \x -> (let id = \y -> y in id x)
-- id's inferred ρ = ["_b", "_b"] (\y -> y has type _b → _b)
-- But x : _a is in Γ when we infer id
-- So Γ = [["_a"]]
test4 :: IO ()
test4 = do
    let rho = ["_b", "_b"]              -- _b → _b
        gamma = [["_a"]]                 -- x : _a in outer scope
        candidates = candidatesForGeneralization rho gamma
    putStrLn $ "Test 4: \\x -> let id = \\y -> y in id x"
    putStrLn $ "  For 'id':"
    putStrLn $ "    ρ = " ++ show rho ++ " (_b → _b)"
    putStrLn $ "    Γ = " ++ show gamma ++ " (x : _a in scope)"
    putStrLn $ "    ftv(ρ) = [\"_b\", \"_b\"]"
    putStrLn $ "    ftv(Γ) = [\"_a\"]"
    putStrLn $ "    ftv(ρ) - ftv(Γ) = " ++ show candidates
    putStrLn $ "  Result: id : ∀b. b → b (generalized - _b not in Γ!)"
    putStrLn ""

-- Test 5: Nested let - outer constrains inner
-- let x = 3 in let y = x in y
-- When inferring y: ρ = ["_a"], Γ = [["_a"]] (x : _a, where _a ~ Int)
test5 :: IO ()
test5 = do
    let rho = ["_a"]                    -- y has type _a (same as x)
        gamma = [["_a"]]                 -- x : _a in env
        candidates = candidatesForGeneralization rho gamma
    putStrLn $ "Test 5: let x = 3 in let y = x in y"
    putStrLn $ "  For 'y':"
    putStrLn $ "    ρ = " ++ show rho
    putStrLn $ "    Γ = " ++ show gamma ++ " (x : _a, _a unified with Int)"
    putStrLn $ "    ftv(ρ) - ftv(Γ) = " ++ show candidates
    putStrLn $ "  Result: y : Int (monomorphic, constrained by x)"
    putStrLn ""

main :: IO ()
main = do
    putStrLn "=== ftv(ρ) - ftv(Γ) Evaluation ==="
    putStrLn ""
    test1
    test2
    test3
    test4
    test5
    putStrLn "=== Summary ==="
    putStrLn "Generalization happens when ftv(ρ) - ftv(Γ) is non-empty."
    putStrLn "This means: variables in the result that are NOT locked by the environment."
