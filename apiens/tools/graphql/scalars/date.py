""" Date/Time types for your API """

import graphql
import pytz  # type: ignore[import]
import datetime
from typing import Any

from apiens.translate import _


def serialize_date_utc(value: datetime.date) -> str:
    return value.isoformat()

def parse_date_utc(value: Any) -> datetime.date:
    try:
        # Any thrown error is reported by GraphQL as "incorrect value". So we don't care about getting a boolean or an integer
        return datetime.date.fromisoformat(value)

        # NOTE: date.fromisoformat() does not support timezone offsets: i.e. "2022-01-01+02:00" is not valid.
        # We do not have to remove it then.
    except Exception as e:
        raise ValueError(_("Not a valid date")) from e

DateUTC = graphql.GraphQLScalarType(
    'DateUTC',
    serialize=serialize_date_utc,
    parse_value=parse_date_utc,
    parse_literal=None,
)


def serialize_datetime_utc(value: datetime.datetime, *, convert: bool = True) -> str:
    # Deal with the timezone.
    # Default behavior: convert
    if convert:
        if value.tzinfo:
            value = value.astimezone(pytz.UTC).replace(tzinfo=None)
    else:
        assert value.tzinfo in (None, datetime.timezone.utc, pytz.utc)

    # Format
    return value.replace(tzinfo=None).isoformat(' ', timespec='seconds') + 'Z'

def parse_datetime_utc(value: Any) -> datetime.datetime:
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

DateTimeUTC = graphql.GraphQLScalarType(
    'DateTimeUTC',
    serialize=serialize_datetime_utc,
    parse_value=parse_datetime_utc,
    parse_literal=None,
)

LiteralDate = graphql.GraphQLScalarType(
    'LiteralDate',
    serialize=serialize_date_utc,
    parse_value=parse_date_utc,
    parse_literal=None,
)


def serialize_literal_time(value: datetime.time) -> str:
    assert value.tzinfo is None  # Literal time must be naive. Not even UTC: just naive.
    return value.isoformat(timespec='seconds')

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

LiteralTime = graphql.GraphQLScalarType(
    'LiteralTime',
    serialize=serialize_literal_time,
    parse_value=parse_literal_time,
    parse_literal=None,
)


def serialize_literal_datetime(value: datetime.datetime) -> str:
    assert value.tzinfo is None  # literal datetime must be naive. Not even UTC: just naive.
    return value.isoformat(' ', timespec='seconds')

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

LiteralDateTime = graphql.GraphQLScalarType(
    'LiteralDateTime',
    serialize=serialize_literal_datetime,
    parse_value=parse_literal_datetime,
    parse_literal=None,
)


def serialize_datetime_with_timezone(value: datetime.datetime) -> str:
    assert value.tzinfo is not None  # must be aware datetime. No assumptions.
    return value.isoformat(' ', timespec='seconds')

def parse_datetime_with_timezone(value: Any) -> datetime.datetime:
    try:
        value = datetime.datetime.fromisoformat(value)
    except Exception as e:
        raise ValueError(_("Not a valid date/time")) from e

    # Require timezone
    if value.tzinfo is None:
        # No assumptions
        raise ValueError(_("Timezone information must be included"))

    # Done
    return value


DateTimeWithTimezone = graphql.GraphQLScalarType(
    'DateTimeWithTimezone',
    serialize=serialize_datetime_with_timezone,
    parse_value=parse_datetime_with_timezone,
    parse_literal=None,
)


def serialize_timezone_name(value: str) -> str:
    return value

def parse_timezone_name(value: Any) -> str:
    try:
        pytz.timezone(value)
    except pytz.UnknownTimeZoneError as e:
        raise ValueError(_("Invalid time zone name")) from e
    else:
        return value

TimezoneName = graphql.GraphQLScalarType(
    'TimezoneName',
    serialize=serialize_timezone_name,
    parse_value=parse_timezone_name,
    parse_literal=None,
)


# Exported definitions
definitions = [
    DateUTC,
    DateTimeUTC,
    LiteralDate,
    LiteralTime,
    LiteralDateTime,
    DateTimeWithTimezone,
    TimezoneName,
]