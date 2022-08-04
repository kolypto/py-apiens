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

from ariadne import ScalarType
from apiens.tools.graphql.scalars import date


DateUTC = ScalarType('DateUTC')
DateUTC.set_serializer(date.serialize_date_utc)
DateUTC.set_value_parser(date.parse_date_utc)

DateTimeUTC = ScalarType('DateTimeUTC')
DateTimeUTC.set_serializer(date.serialize_datetime_utc)
DateTimeUTC.set_value_parser(date.parse_datetime_utc)

LiteralDate = ScalarType('LiteralDate')
LiteralDate.set_serializer(date.serialize_date_utc)
LiteralDate.set_value_parser(date.parse_date_utc)

LiteralTime = ScalarType('LiteralTime')
LiteralTime.set_serializer(date.serialize_literal_time)
LiteralTime.set_value_parser(date.parse_literal_time)

LiteralDateTime = ScalarType('LiteralDateTime')
LiteralDateTime.set_serializer(date.serialize_literal_datetime)
LiteralDateTime.set_value_parser(date.parse_literal_datetime)

DateTimeWithTimezone = ScalarType('DateTimeWithTimezone')
DateTimeWithTimezone.set_serializer(date.serialize_datetime_with_timezone)
DateTimeWithTimezone.set_value_parser(date.parse_datetime_with_timezone)

TimezoneName = ScalarType('TimezoneName')
TimezoneName.set_serializer(date.serialize_timezone_name)
TimezoneName.set_value_parser(date.parse_timezone_name)


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