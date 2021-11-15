from enum import Enum
from typing import Any

import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg


class StrEnum(sa.Enum):
    """ An Enum type backed by a VARCHAR """

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
        assert self.length <= 64  # not too long
        self.length = 64  # make it sufficiently


class JSONBKeyedBy(sa.TypeDecorator):
    """ A JSONB object with ENUM keys """
    impl = pg.JSONB

    def __init__(self, EnumType: type[Enum]):
        super().__init__()
        self._EnumType = EnumType

    def process_bind_param(self, value: dict[Enum, Any], dialect) -> dict[str, Any]:
        if value is None:
            value = {}

        return {
            k.name: v
            for k, v in value.items()
        }

    def process_result_value(self, value: dict[str, Any], dialect) -> dict[Enum, Any]:
        if value is None:
            value = {}

        return {
            self._EnumType[k]: v
            for k, v in value.items()
        }
