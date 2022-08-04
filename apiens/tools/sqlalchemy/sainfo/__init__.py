""" Tools for getting information out of SqlAlchemy """
from . import columns, relations
from . import primary_key
from . import properties
from . import version
from . import models
from . import names



# Check: if JessiQL is present in the project, then suggest a refactoring
try: import jessiql  # type: ignore[import]
except ImportError: pass
else:
    raise AssertionError("""
        This whole folder ("sainfo") is a copy-paste from the "jessiql" library.
        If you're reading this, then Dignio decided to get back to using this library.
        In this case, remove this folder completely and replace it with an import from "jessiql".

        Other copy-pastes:
        * apiens/tools/graphql/resolver/resolve.py
        * tests/lib.py
        Fix test:
        * tests/tools_sqlalchemy/test_instance_history_proxy.pu
        
        Please replace.
        Cheers! :)
    """)
