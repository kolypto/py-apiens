from __future__ import annotations

from typing import TypeVar, Generic, TYPE_CHECKING

import sqlalchemy as sa
import sqlalchemy.orm

if TYPE_CHECKING:
    from ..crudparams import CrudParams


# SqlAlchemy instance object
SAInstanceT = TypeVar('SAInstanceT', bound=object)


class ModelOperationBase(Generic[SAInstanceT]):
    """ Base class for Model operations: queries and mutations """
    # CRUD settings: the static container for all the configuration of this CRUD handler.
    params: CrudParams

    # The database session to use
    ssn: sa.orm.Session

    def __init__(self, ssn: sa.orm.Session, params: CrudParams):
        self.ssn = ssn
        self.params = params
