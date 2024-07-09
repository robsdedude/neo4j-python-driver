from __future__ import annotations

import logging
import types
import typing as t


log = logging.getLogger("neo4j")


__all__ = [
    "np",
    "pd",
    "rust_available",
    "rust_ext",
]



#############
### numpy ###
#############
np: t.Any = None

try:
    import numpy as np  # type: ignore[no-redef]
except ImportError:
    pass


##############
### pandas ###
##############
pd: t.Any = None

try:
    import pandas as pd  # type: ignore[no-redef]
except ImportError:
    pass


#######################
### Rust extensions ###
#######################
def _load_rust_ext() -> t.Optional[types.ModuleType]:
    try:
        import neo4j_py  # marker package to not load any Rust extensions
        log.info(
            "[     ]  _: <RUST EXT> extensions disabled through neo4j-py."
        )
        return None
    except ImportError:
        pass

    try:
        from .. import _rust as rust_ext  # type: ignore[no-redef]
        log.info("[     ]  _: <RUST EXT> Driver's own extensions picked up.")
        return rust_ext
    except ImportError:
        pass

    try:
        from neo4j_rust_ext import _rust as rust_ext  # type: ignore[no-redef]
        log.info(
            "[     ]  _: <RUST EXT> neo4j-rust-ext picked up."
        )
        return rust_ext
    except ImportError:
        pass

    log.info("[     ]  _: <RUST EXT> No extensions found.")
    return None


rust_ext: t.Optional[types.ModuleType] = _load_rust_ext()
rust_available = rust_ext is not None
