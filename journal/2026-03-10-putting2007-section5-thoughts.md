# Putting 2007 Implementation Thoughts

**Date:** 2026-03-10  
**Topic:** Section 5 - Meta Type Variables and Unification (Damas-Milner)
**Status:** Raw thinking - may contain errors

---

## Notes on Section 5

Reading the section on meta type variables and unification. This is the Damas-Milner style system with syntax-directed rules.

Key observations:
- Poly types (σ) are **only** introduced by `let` expressions
- Variables in a `let` body can use poly types from the binding
- Type annotations `(t :: σ)` create poly types but get **instantiated immediately**

This seems to be the restriction that makes inference decidable without needing annotations everywhere. In Damas-Milner, you can't have polymorphic function parameters - only `let`-bound values can be polymorphic.

## Implementation Detail: MetaTv Chain

Looking at the Haskell implementation:

```haskell
data MetaTv = Meta Uniq (IORef (Maybe Tau))
```

So `MetaTv` contains a `TyRef` which is `IORef (Maybe Tau)`. The `Tau` here can itself be another `MetaTv`.

**My understanding:** The unification works like a chain:
1. A `MetaTv` starts with `Nothing` (unknown)
2. When unified with a concrete type, it becomes `Just tau`
3. When unified with another `MetaTv`, it might point to that `MetaTv`
4. Resolving requires following the chain - if `Just tau` and `tau` is itself a `MetaTv`, keep following

This is essentially union-find with path compression, I think? The `IORef` gives mutation for efficient in-place updates.

**Questions I have:**
- How does the occurs check work with this chain structure?
- When do you compress the path vs just follow it?
- Is there a difference between "unbound meta" vs "bound to another meta"?

## Contrast with Full Higher-Rank

Section 5 is just Damas-Milner (rank-1). The paper builds up to higher-rank in later sections. The key difference is:

- **Damas-Milner (Section 5):** Poly types only at `let`
- **Higher-rank (Section 6+):** Poly types can appear in function arguments like `(∀a. a → a) → Int`

I need to understand Section 5 well before moving to the bidirectional system (Figure 8) which handles arbitrary rank.

## Unresolved Thoughts

1. The instantiation judgment `⊢^inst_δ σ ≤ ρ ↦ f` - this seems to be the bridge between poly types and monomorphic use
2. Deep skolemization (Section 4.6) - how does this relate to the unification algorithm?
3. The relationship between `pr(σ)` (prenex conversion) and unification

Need to re-read these sections carefully.

---

**Next Steps:**
- Re-read Section 4.6 (Deep Skolemization)
- Compare with the implementation in `putting-2007-implementation.hs`
- Figure out how the bidirectional rules (Figure 8) extend the Damas-Milner base
