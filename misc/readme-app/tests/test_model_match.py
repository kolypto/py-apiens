from apiens.testing import model_match

def test_model_match():
    def main():
        # Convert every model to its intermediate shape
        db_user = model_match.match(User)
        pd_user = model_match.match(UserSchema)

        # Compare DB `User` model to Pydantic `UserSchema`    
        assert pd_user == model_match.select_fields(
            # Exclude a few fields from comparison
            db_user,
            model_match.exclude('password'),
        )

    # Models
    import sqlalchemy as sa
    import sqlalchemy.orm
    import sqlalchemy.ext.declarative

    Base = sa.ext.declarative.declarative_base()

    class User(Base):
        __tablename__ = 'users'

        id = sa.Column(sa.Integer, primary_key=True)
        login = sa.Column(sa.String)
        password = sa.Column(sa.String)

    import pydantic as pd
    from typing import Optional

    class UserSchema(pd.BaseModel):
        id: int 
        login: Optional[str]

    # Go
    main()