from enum import Enum
import sqlalchemy as sa


class StrEnum(sa.Enum):
    """ An Enum type backed by a VARCHAR 
    
    Example:
        class AccountType(Enum):
            ADMIN = 'admin'
            VISITOR = 'visitor'

        class User(Base):
            ...
            account_type = sa.Column(StrEnum(AccountType), nullable=False)
    """

    def __init__(self, *enums: type[Enum], **kwargs):
        # Neither are explicitly set to True
        assert kwargs.get('native_enum') is not True
        assert kwargs.get('create_constraint') is not True

        # Both False, because hard to migrate
        kwargs['native_enum'] = False
        kwargs['create_constraint'] = False

        # super()
        super().__init__(*enums, **kwargs)

        # Make sure every such field is "long enough"
        # Otherwise, new, longer enum values may get truncated
        assert self.length <= 64  # type: ignore[operator]
        self.length = 64  # make it sufficiently long
