import sqlalchemy as sa
import sqlalchemy.orm

from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = sa.Column(sa.String, nullable=False, primary_key=True)
    login = sa.Column(sa.String, nullable=False)


class Article(Base):
    __tablename__ = 'articles'

    id = sa.Column(sa.String, nullable=False, primary_key=True)
    title = sa.Column(sa.String, nullable=False)

    author_id = sa.Column(User.id.type, sa.ForeignKey(User.id), nullable=False)
