""" Date/Time types for your API

Usage:
    from apiens.tools.ariadne.schema import load_schema_from_module
    import apiens.tools.ariadne.scalars.date
    schema = ariadne.make_executable_schema([
            ariadne.load_schema_from_path(os.path.dirname(__file__)),
            load_schema_from_module(apiens.tools.ariadne.scalars, 'date.graphql'),
        ],
        apiens.tools.ariadne.scalars.date.definitions,
    )
"""

import pytz
import gettext
import datetime
from typing import Any
from ariadne import ScalarType


# Init translations
# TODO: will this work with lazy translations?
try:
    translation = gettext.translation('apiens')
except FileNotFoundError:
    translation = gettext.NullTranslations()
_ = translation.gettext


DateUTC = ScalarType('DateUTC')

@DateUTC.serializer
def serialize_date_utc(value: datetime.date) -> str:
    return value.isoformat()

@DateUTC.value_parser
def parse_date_utc(value: Any) -> datetime.date:
    try:
        # Any thrown error is reported by GraphQL as "incorrect value". So we don't care about getting a boolean or an integer
        return datetime.date.fromisoformat(value)

        # NOTE: date.fromisoformat() does not support timezone offsets: i.e. "2022-01-01+02:00" is not valid.
        # We do not have to remove it then.
    except Exception as e:
        raise ValueError(_("Not a valid date")) from e


DateTimeUTC = ScalarType('DateTimeUTC')

@DateTimeUTC.serializer
def serialize_datetime_utc(value: datetime.datetime) -> str:
    assert value.tzinfo in (None, datetime.timezone.utc, pytz.utc)
    return value.replace(tzinfo=None).isoformat(' ', timespec='seconds') + 'Z'

@DateTimeUTC.value_parser
def parse_datetime_utc(value: Any) -> datetime:
    try:
        # RFC3339 supports "Z" offset. Our ISO parser does not.
        value = value.removesuffix('Z')
        value = datetime.datetime.fromisoformat(value)
    except Exception as e:
        raise ValueError(_("Not a valid date/time")) from e

    # If the timezone was given -- convert to UTC and make it naive
    if value.tzinfo is not None:
        value = value.astimezone(pytz.UTC).replace(tzinfo=None)

    # Done
    return value


LiteralDate = ScalarType('LiteralDate')
LiteralDate.set_serializer(serialize_date_utc)
LiteralDate.set_value_parser(parse_date_utc)


LiteralTime = ScalarType('LiteralTime')

@LiteralTime.serializer
def serialize_literal_time(value: datetime.time) -> str:
    assert value.tzinfo is None  # Literal time must be naive. Not even UTC: just naive.
    return value.isoformat(timespec='seconds')

@LiteralTime.value_parser
def parse_literal_time(value: Any) -> datetime.time:
    try:
        value = datetime.time.fromisoformat(value)
    except Exception as e:
        raise ValueError(_("Not a valid time")) from e

    # NOTE: time.fromisoformat() supports timezone offsets: "00:00+02:00" is supported.
    # We need to make sure that the user cannot do this.
    if value.tzinfo is not None:
        raise ValueError(_("Literal time cannot have timezone associated with it"))

    # Done
    return value


LiteralDateTime = ScalarType('LiteralDateTime')

@LiteralDateTime.serializer
def serialize_literal_datetime(value: datetime.datetime) -> str:
    assert value.tzinfo is None  # literal datetime must be naive. Not even UTC: just naive.
    return value.isoformat(' ', timespec='seconds')

@LiteralDateTime.value_parser
def parse_literal_datetime(value: Any) -> datetime.datetime:
    try:
        value = datetime.datetime.fromisoformat(value)
    except Exception as e:
        raise ValueError(_("Not a valid date/time")) from e

    # Reject timezone
    if value.tzinfo is not None:
        raise ValueError(_("Timezones not allowed with literal date/times"))

    # Done
    return value


TimezoneName = ScalarType('TimezoneName')

@TimezoneName.value_parser
def parse_timezone_name(value: Any) -> str:
    try:
        pytz.timezone(value)
    except pytz.UnknownTimeZoneError as e:
        raise ValueError(_("Invalid time zone name")) from e
    else:
        return value


# Exported definitions
definitions = [
    DateUTC,
    DateTimeUTC,
    LiteralDate,
    LiteralTime,
    LiteralDateTime,
]