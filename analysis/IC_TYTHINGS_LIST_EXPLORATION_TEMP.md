# GHC InteractiveContext ic_tythings Exploration

**Topic:** Why does `ic_tythings` keep a growing list of all definitions rather than just the currently visible ones?

**Central Question:** What is the fundamental purpose of accumulating all TyThings in `ic_tythings`? Why not discard shadowed definitions?

**Date:** 2026-03-30

---

## Summary

The `ic_tythings` field in GHC's `InteractiveContext` accumulates ALL TyThings (Ids, TyCons, Classes) defined at the GHCi prompt, including shadowed definitions. This design is intentional and serves multiple critical purposes: (1) enabling access to shadowed bindings via qualified names, (2) supporting the debugger's breakpoint restoration mechanism, (3) allowing type environment reconstruction for type checking and Core Lint, and (4) maintaining the semantics that each original name M.T refers to exactly one unique thing.

---

## Claims

### Claim 1: ic_tythings Accumulates All Definitions Including Shadowed Ones

**Statement:** The `ic_tythings` field grows unboundedly by prepending new TyThings to the front of the list. Shadowed definitions are NEVER removed from the underlying storage.

**Source:** `/home/liu/Documents/bub/upstream/ghc/compiler/GHC/Runtime/Context.hs:289-294, 418`

**Evidence:**
```haskell
-- Field definition with comment explaining the order
ic_tythings   :: [TyThing],
    -- ^ TyThings defined by the user, in reverse order of
    -- definition (ie most recent at the front).
    -- Also used in GHC.Tc.Module.runTcInteractive to fill the type
    -- checker environment.
    -- See Note [ic_tythings]

-- In extendInteractiveContext (line 418):
, ic_tythings   = new_tythings ++ ic_tythings ictxt
```

**Status:** Draft

**Notes:** The prepend semantics ensure that when traversing the list, newer definitions are encountered first, enabling shadowing to work correctly during name resolution.

---

### Claim 2: Shadowed Bindings Remain Accessible via Qualified Names

**Statement:** Shadowed definitions are retained in `ic_tythings` so they can still be accessed using their qualified names (e.g., `Ghci1.foo` even after `Ghci2.foo` shadows it unqualified).

**Source:** `/home/liu/Documents/bub/upstream/ghc/compiler/GHC/Runtime/Context.hs:48-106 (Note [The interactive package])`

**Evidence:**
```haskell
{- Note [The interactive package]
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Type, class, and value declarations at the command prompt are treated
as if they were defined in modules
   interactive:Ghci1
   interactive:Ghci2
   ...etc...
with each bunch of declarations using a new module, all sharing a
common package 'interactive'.

This scheme deals well with shadowing.  For example:

   ghci> data T = A
   ghci> data T = B
   ghci> :i A
   data Ghci1.T = A  -- Defined at <interactive>:2:10

Here we must display info about constructor A, but its type T has been
shadowed by the second declaration.  But it has a respectable
qualified name (Ghci1.T), and its source location says where it was
defined, and it can also be used with the qualified name.

So the main invariant continues to hold, that in any session an
original name M.T only refers to one unique thing.
-}
```

**Status:** Draft

**Notes:** This is a fundamental design invariant - original names must remain unique and resolvable. If shadowed definitions were deleted, their qualified names would become dangling references.

---

### Claim 3: The Debugger Requires Full ic_tythings History for Breakpoint Restoration

**Statement:** The debugger uses `ic_tythings` to save and restore the interactive context when entering and leaving breakpoints. Without the full history, breakpoint resumption would lose bindings.

**Source:** `/home/liu/Documents/bub/upstream/ghc/compiler/GHC/Runtime/Eval.hs:421-432`

**Evidence:**
```haskell
-- From resumeExec function:
let (resume_tmp_te,resume_gre_cache) = resumeBindings r
    ic' = ic { ic_tythings = resume_tmp_te,
               ic_gre_cache = resume_gre_cache,
               ic_resume   = rs }
setSession hsc_env{ hsc_IC = ic' }

-- remove any bindings created since the breakpoint from the linker's environment
let old_names = map getName resume_tmp_te
    new_names = [ n | thing <- ic_tythings ic
                    , let n = getName thing
                    , not (n `elem` old_names) ]
```

**Status:** Draft

**Notes:** When resuming from a breakpoint, the debugger must restore the exact state from before the breakpoint. This requires saving a snapshot of `ic_tythings` in the `Resume` structure.

---

### Claim 4: Type Checking Requires Complete TyThings for Type Environment Construction

**Statement:** The type checker uses the full `ic_tythings` list to construct the type environment (`tcg_type_env`) when typechecking interactive input. Shadowed definitions may still be referenced in types.

**Source:** `/home/liu/Documents/bub/upstream/ghc/compiler/GHC/Tc/Module.hs:2167, 2181-2184`

**Evidence:**
```haskell
-- In runTcInteractive:
(lcl_ids, top_ty_things) = partitionWith is_closed (ic_tythings icxt)

type_env1 = mkTypeEnvWithImplicits top_ty_things
type_env  = extendTypeEnvWithIds type_env1
          $ map instanceDFunId (instEnvElts ic_insts)
            -- Putting the dfuns in the type_env
            -- is just to keep Core Lint happy
```

**Status:** Draft

**Notes:** Even shadowed definitions may appear in the types of currently-visible bindings. The type environment must contain ALL TyThings that could be referenced.

---

### Claim 5: Core Lint Requires Full ic_tythings for In-Scope Variable Checking

**Statement:** The Core Lint pass uses `ic_tythings` to determine which variables are in scope when linting interactive expressions. Without the full list, Lint would report valid variables as out of scope.

**Source:** `/home/liu/Documents/bub/upstream/ghc/compiler/GHC/Core/Lint/Interactive.hs:38-46`

**Evidence:**
```haskell
interactiveInScope :: InteractiveContext -> [Var]
-- In GHCi we may lint expressions, or bindings arising from 'deriving'
-- clauses, that mention variables bound in the interactive context.
-- These are Local things (see Note [Interactively-bound Ids in GHCi] in GHC.Runtime.Context).
-- So we have to tell Lint about them, lest it reports them as out of scope.
--
-- See #8215 for an example
interactiveInScope ictxt
  = tyvars ++ ids
  where
    (cls_insts, _fam_insts) = ic_instances ictxt
    te1    = mkTypeEnvWithImplicits (ic_tythings ictxt)
    te     = extendTypeEnvWithIds te1 (map instanceDFunId $ instEnvElts cls_insts)
    ids    = typeEnvIds te
```

**Status:** Draft

**Notes:** This is crucial for validating generated Core code. Interactive bindings can appear in derived code or expressions being linted.

---

### Claim 6: icInScopeTTs Only Filters for DISPLAY Purposes

**Statement:** The `icInScopeTTs` function filters `ic_tythings` to show only unshadowed bindings, but this filtering is ONLY for display purposes (e.g., `:showBindings`). The underlying `ic_tythings` list remains unchanged.

**Source:** `/home/liu/Documents/bub/upstream/ghc/compiler/GHC/Runtime/Context.hs:389-397`

**Evidence:**
```haskell
-- | This function returns the list of visible TyThings (useful for
-- e.g. showBindings).
--
-- It picks only those TyThings that are not shadowed by later definitions on the interpreter,
-- to not clutter :showBindings with shadowed ids, which would show up as Ghci9.foo.
--
-- Some TyThings define many names; we include them if _any_ name is still
-- available unqualified.
icInScopeTTs :: InteractiveContext -> [TyThing]
icInScopeTTs ictxt = filter in_scope_unqualified (ic_tythings ictxt)
  where
    in_scope_unqualified thing = or
        [ unQualOK gre
        | gre <- tyThingLocalGREs thing
        , let name = greName gre
        , Just gre <- [lookupGRE_Name (icReaderEnv ictxt) name]
        ]
```

**Status:** Draft

**Notes:** The comment explicitly states this is to avoid cluttering `:showBindings` with shadowed ids. This confirms that filtering is a UI concern, not a semantic requirement.

---

### Claim 7: The Design Explicitly Acknowledges Memory Cost for Time Efficiency

**Statement:** GHC developers explicitly acknowledge that `ic_tythings` can contain "many entries that shadow each other" and that reconstructing the environment from scratch would be "quite expensive." The design accepts unbounded memory growth to maintain O(1) incremental updates.

**Source:** `/home/liu/Documents/bub/upstream/ghc/compiler/GHC/Runtime/Context.hs:248-256 (Note [icReaderEnv recalculation])`

**Evidence:**
```haskell
{- Note [icReaderEnv recalculation]
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The GlobalRdrEnv describing what's in scope at the prompts consists
of all the imported things, followed by all the things defined on the prompt,
with shadowing. Defining new things on the prompt is easy: we shadow as needed,
and then extend the environment.

But changing the set of imports, which can happen later as well, is tricky
we need to re-apply the shadowing from all the things defined at the prompt!

For example:

    ghci> let empty = True
    ghci> import Data.IntMap.Strict     -- Exports 'empty'
    ghci> empty   -- Still gets the 'empty' defined at the prompt
    True

It would be correct to re-construct the env from scratch based on
`ic_tythings`, but that'd be quite expensive if there are many entries in
`ic_tythings` that shadow each other.
-}
```

**Status:** Draft

**Notes:** This is a classic time-space tradeoff. The implementation uses `igre_prompt_env` (a cache of visible prompt definitions) to make import changes efficient without reconstructing from the full `ic_tythings`.

---

### Claim 8: The Interactive Package Design Requires Persistent Original Names

**Statement:** The "interactive package" design assigns each GHCi input a unique module name (Ghci1, Ghci2, etc.). This design REQUIRES that all definitions persist because each has a unique original name that must remain valid for the entire session.

**Source:** `/home/liu/Documents/bub/upstream/ghc/compiler/GHC/Runtime/Context.hs:48-76`

**Evidence:**
```haskell
{- Note [The interactive package]
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Type, class, and value declarations at the command prompt are treated
as if they were defined in modules
   interactive:Ghci1
   interactive:Ghci2
   ...etc...
with each bunch of declarations using a new module, all sharing a
common package 'interactive'.

The details are a bit tricky though:

 * The field ic_mod_index counts which Ghci module we've got up to.
   It is incremented when extending ic_tythings

 * ic_tythings contains only things from the 'interactive' package.

So the main invariant continues to hold, that in any session an
original name M.T only refers to one unique thing.  (In a previous
iteration both the T's above were called :Interactive.T, albeit with
different uniques, which gave rise to all sorts of trouble.)
-}
```

**Status:** Draft

**Notes:** The note mentions that a previous iteration used the same module name with different uniques, which "gave rise to all sorts of trouble." The current design solves this by giving each definition a unique module name, but this requires keeping all definitions.

---

### Claim 9: DFunIds Are Explicitly Excluded from ic_tythings

**Statement:** Dictionary function Ids (DFunIds) are deliberately NOT stored in `ic_tythings` because they can be reconstructed from `ic_instances`. This is an intentional optimization to avoid redundancy.

**Source:** `/home/liu/Documents/bub/upstream/ghc/compiler/GHC/Runtime/Context.hs:215-217`

**Evidence:**
```haskell
{- Note [ic_tythings]
~~~~~~~~~~~~~~~~~~
The ic_tythings field contains
  * The TyThings declared by the user at the command prompt
    (eg Ids, TyCons, Classes)

  * The user-visible Ids that arise from such things, which
    *don't* come from 'implicitTyThings', notably:
       - record selectors
       - class ops
    The implicitTyThings are readily obtained from the TyThings
    but record selectors etc are not

It does *not* contain
  * DFunIds (they can be gotten from ic_instances)
  * CoAxioms (ditto)
-}
```

**Status:** Draft

**Notes:** This confirms that the design is intentional about what goes into `ic_tythings`. DFunIds are excluded because they're derivable from instances, but record selectors are included because they cannot be easily reconstructed.

---

### Claim 10: Shadowing Affects GlobalRdrEnv, Not ic_tythings Storage

**Statement:** Name shadowing is implemented at the `GlobalRdrEnv` level (the name resolution environment), NOT by removing entries from `ic_tythings`. Both the shadowing and shadowed definitions coexist in storage; only visibility differs.

**Source:** `/home/liu/Documents/bub/upstream/ghc/compiler/GHC/Runtime/Context.hs:459-463, 467-481`

**Evidence:**
```haskell
-- replaceImportEnv: Rebuilds the GlobalRdrEnv when imports change
replaceImportEnv :: IcGlobalRdrEnv -> GlobalRdrEnv -> IcGlobalRdrEnv
replaceImportEnv igre import_env = igre { igre_env = new_env }
  where
    import_env_shadowed = shadowNames False import_env (igre_prompt_env igre)
    new_env = import_env_shadowed `plusGlobalRdrEnv` igre_prompt_env igre

-- icExtendGblRdrEnv: Adds TyThings with shadowing
icExtendGblRdrEnv :: Bool -> GlobalRdrEnv -> [TyThing] -> GlobalRdrEnv
icExtendGblRdrEnv drop_only_qualified env tythings
  = foldr add env tythings  -- Foldr makes things in the front of
                            -- the list shadow things at the back
  where
    -- One at a time, to ensure each shadows the previous ones
    add thing env
       | is_sub_bndr thing
       = env
       | otherwise
       = foldl' extendGlobalRdrEnv env1 new_gres
       where
          new_gres = tyThingLocalGREs thing
          env1     = shadowNames drop_only_qualified env $ mkGlobalRdrEnv new_gres
```

**Status:** Draft

**Notes:** The `shadowNames` function creates shadowed entries in the GlobalRdrEnv, but the underlying TyThings remain in `ic_tythings`. This is a separation of concerns: storage (`ic_tythings`) vs. visibility (`GlobalRdrEnv`).

---

## Key Design Decisions Summary

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Storage** | Keep all TyThings | Qualified access, debugger restoration, type environment |
| **Shadowing** | At GlobalRdrEnv level | Efficient incremental updates without list rebuilding |
| **Order** | Reverse chronological | Natural shadowing semantics (first match wins) |
| **DFunIds** | Excluded | Reconstructible from instances |
| **Record selectors** | Included | Not reconstructible from TyCon alone |

## What Would Break If Definitions Were Deleted?

1. **Qualified access**: `Ghci1.foo` would become a dangling reference after `foo` is redefined
2. **Debugger resumption**: Breakpoint restoration would lose bindings created after the breakpoint
3. **Type checking**: Types referencing shadowed definitions would become ill-formed
4. **Core Lint**: Valid Core code referencing shadowed bindings would fail validation
5. **The "original name" invariant**: Each M.T would no longer refer to exactly one unique thing

## Conclusion

The accumulation of all TyThings in `ic_tythings` is not a memory leak or oversight - it is a **fundamental design requirement** of GHC's interactive system. The design intentionally trades unbounded memory growth for:
- Correct semantics (original name invariant)
- Efficient incremental updates
- Full debugger functionality
- Complete type checking
- Access to shadowed bindings via qualified names
