"""Surface language AST for System F.

Surface syntax uses name-based binding (not de Bruijn indices) and allows
omitting type annotations where they can be inferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from systemf.utils.location import Location


# =============================================================================
# Surface Types
# =============================================================================


class SurfaceType:
    """Base class for surface types."""

    pass


@dataclass(frozen=True)
class SurfaceTypeVar(SurfaceType):
    """Type variable: a."""

    name: str
    location: Location

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class SurfaceTypeArrow(SurfaceType):
    """Function type: arg -> ret."""

    arg: SurfaceType
    ret: SurfaceType
    location: Location

    def __str__(self) -> str:
        arg_str = f"({self.arg})" if isinstance(self.arg, SurfaceTypeArrow) else str(self.arg)
        return f"{arg_str} -> {self.ret}"


@dataclass(frozen=True)
class SurfaceTypeForall(SurfaceType):
    """Polymorphic type: forall a. body."""

    var: str
    body: SurfaceType
    location: Location

    def __str__(self) -> str:
        return f"forall {self.var}. {self.body}"


@dataclass(frozen=True)
class SurfaceTypeConstructor(SurfaceType):
    """Data type constructor: T t1 ... tn."""

    name: str
    args: list[SurfaceType]
    location: Location

    def __str__(self) -> str:
        if not self.args:
            return self.name
        args_str = " ".join(
            f"({arg})" if isinstance(arg, (SurfaceTypeArrow, SurfaceTypeForall)) else str(arg)
            for arg in self.args
        )
        return f"{self.name} {args_str}"


SurfaceTypeRepr = Union[SurfaceTypeVar, SurfaceTypeArrow, SurfaceTypeForall, SurfaceTypeConstructor]


# =============================================================================
# Surface Terms
# =============================================================================


class SurfaceTerm:
    """Base class for surface terms."""

    pass


@dataclass(frozen=True)
class SurfaceVar(SurfaceTerm):
    """Variable reference by name: x."""

    name: str
    location: Location

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class SurfaceAbs(SurfaceTerm):
    """Lambda abstraction: \\x -> body or \\x:T -> body."""

    var: str
    var_type: Optional[SurfaceType]
    body: SurfaceTerm
    location: Location

    def __str__(self) -> str:
        if self.var_type:
            return f"\\{self.var}:{self.var_type} -> {self.body}"
        return f"\\{self.var} -> {self.body}"


@dataclass(frozen=True)
class SurfaceApp(SurfaceTerm):
    """Function application: f arg."""

    func: SurfaceTerm
    arg: SurfaceTerm
    location: Location

    def __str__(self) -> str:
        return f"({self.func} {self.arg})"


@dataclass(frozen=True)
class SurfaceTypeAbs(SurfaceTerm):
    """Type abstraction: /\\a. body (written as /\\a. or Λa.)."""

    var: str
    body: SurfaceTerm
    location: Location

    def __str__(self) -> str:
        return f"/\\{self.var}. {self.body}"


@dataclass(frozen=True)
class SurfaceTypeApp(SurfaceTerm):
    """Type application: func @type or func [type]."""

    func: SurfaceTerm
    type_arg: SurfaceType
    location: Location

    def __str__(self) -> str:
        return f"({self.func} @{self.type_arg})"


@dataclass(frozen=True)
class SurfaceLet(SurfaceTerm):
    """Let binding: let name = value in body."""

    name: str
    value: SurfaceTerm
    body: SurfaceTerm
    location: Location

    def __str__(self) -> str:
        return f"let {self.name} = {self.value} in {self.body}"


@dataclass(frozen=True)
class SurfaceAnn(SurfaceTerm):
    """Type annotation: term : type."""

    term: SurfaceTerm
    type: SurfaceType
    location: Location

    def __str__(self) -> str:
        return f"({self.term} : {self.type})"


@dataclass(frozen=True)
class SurfaceConstructor(SurfaceTerm):
    """Data constructor application: Con args."""

    name: str
    args: list[SurfaceTerm]
    location: Location

    def __str__(self) -> str:
        if not self.args:
            return self.name
        args_str = " ".join(str(arg) for arg in self.args)
        return f"({self.name} {args_str})"


@dataclass(frozen=True)
class SurfacePattern:
    """Pattern in a case branch: Con vars."""

    constructor: str
    vars: list[str]
    location: Location

    def __str__(self) -> str:
        if self.vars:
            return f"{self.constructor} {' '.join(self.vars)}"
        return self.constructor


@dataclass(frozen=True)
class SurfaceBranch:
    """Case branch: pattern -> body."""

    pattern: SurfacePattern
    body: SurfaceTerm
    location: Location

    def __str__(self) -> str:
        return f"{self.pattern} -> {self.body}"


@dataclass(frozen=True)
class SurfaceCase(SurfaceTerm):
    """Pattern matching: case scrutinee of branches."""

    scrutinee: SurfaceTerm
    branches: list[SurfaceBranch]
    location: Location

    def __str__(self) -> str:
        branches_str = " | ".join(str(branch) for branch in self.branches)
        return f"case {self.scrutinee} of {{ {branches_str} }}"


SurfaceTermRepr = Union[
    SurfaceVar,
    SurfaceAbs,
    SurfaceApp,
    SurfaceTypeAbs,
    SurfaceTypeApp,
    SurfaceLet,
    SurfaceAnn,
    SurfaceConstructor,
    SurfaceCase,
]


# =============================================================================
# Surface Declarations
# =============================================================================


class SurfaceDeclaration:
    """Base class for surface declarations."""

    pass


@dataclass(frozen=True)
class SurfaceDataDeclaration(SurfaceDeclaration):
    """Data type declaration: data Name params = Con1 args1 | Con2 args2 | ..."""

    name: str
    params: list[str]
    constructors: list[tuple[str, list[SurfaceType]]]
    location: Location

    def __str__(self) -> str:
        params_str = " ".join(self.params) if self.params else ""
        constrs_str = " | ".join(
            f"{name} {' '.join(str(t) for t in types)}" for name, types in self.constructors
        )
        return f"data {self.name} {params_str} = {constrs_str}"


@dataclass(frozen=True)
class SurfaceTermDeclaration(SurfaceDeclaration):
    """Term declaration: name : type = body or name = body."""

    name: str
    type_annotation: Optional[SurfaceType]
    body: SurfaceTerm
    location: Location

    def __str__(self) -> str:
        if self.type_annotation:
            return f"{self.name} : {self.type_annotation} = {self.body}"
        return f"{self.name} = {self.body}"


SurfaceDeclarationRepr = Union[SurfaceDataDeclaration, SurfaceTermDeclaration]
