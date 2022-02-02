from __future__ import annotations

from contextlib import contextmanager

import sqlalchemy as sa
import sqlalchemy.orm


class SASessionMixin:
    """ A mixin for your Crud if you want to have a shortcut for handling your sessions """

    # The database session to use
    ssn: sa.orm.Session

    @contextmanager
    def transaction(self):
        """ Wrap a section of code into a Crud transaction. commit() if everything goes fine; rollback() if not

        Example:
            with UserCrud(ssn).transaction() as crud:
                user = crud.update(user, id=id)
                return {'user': user}
        """
        try:
            yield self
        except Exception:
            self.rollback()
            raise
        else:
            self.commit()

    def commit(self) -> sa.orm.Session:
        """ Actually commit the changes.

        Note that no other place in this class performs a commit!
        You have to call it when you're done with this CRUD object.
        """
        self.ssn.commit()
        return self.ssn

    def rollback(self) -> sa.orm.Session:
        """ Send signals and Session.rollback() """
        self.ssn.rollback()
        return self.ssn
