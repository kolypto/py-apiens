from enum import Enum
from typing import Any

import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg


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
