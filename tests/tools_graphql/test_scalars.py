import datetime
import pytest
import pytz
from apiens.tools.ariadne.scalars.date import DateUTC, DateTimeUTC, LiteralDate, LiteralTime, LiteralDateTime, DateTimeWithTimezone


def test_scalars_date():
    """ Test scalars.date """

    # === DateUTC
    assert DateUTC._parse_value('2022-12-31') == datetime.date(2022, 12, 31)
    assert DateUTC._serialize(datetime.date(2022, 12, 31)) == '2022-12-31'

    # === DateTimeUTC
    d_23_59 = datetime.datetime(2022, 12, 31, 23, 59, 0)
    moscow = datetime.timezone(datetime.timedelta(hours=2))
    assert DateTimeUTC._parse_value('2022-12-31 23:59') == d_23_59
    assert DateTimeUTC._parse_value('2022-12-31 23:59:00') == d_23_59
    assert DateTimeUTC._parse_value('2022-12-31 23:59:00Z') == d_23_59
    assert DateTimeUTC._parse_value('2022-12-31 23:59:00+00:00') == d_23_59
    assert DateTimeUTC._serialize(d_23_59) == '2022-12-31 23:59:00Z'

    # Okay, what about aware datetimes?
    # Input: converted to UTC
    assert DateTimeUTC._parse_value('2022-12-31 23:59:00+02:00') == datetime.datetime(2022, 12, 31, 23 - 2, 59, 0)  # converted
    # Output: convered to UTC
    assert DateTimeUTC._serialize(d_23_59.replace(tzinfo=pytz.UTC)) == '2022-12-31 23:59:00Z'
    assert DateTimeUTC._serialize(d_23_59.replace(tzinfo=moscow)) == '2022-12-31 21:59:00Z'

    # === LiteralDate
    assert LiteralDate._parse_value('2022-12-31') == datetime.date(2022, 12, 31)
    assert LiteralDate._serialize(datetime.date(2022, 12, 31)) == '2022-12-31'

    # === LiteralTime
    assert LiteralTime._parse_value('00:00') == datetime.time(0, 0)
    assert LiteralTime._serialize(datetime.time(0, 0))

    # Aware times
    # Input: error
    with pytest.raises(ValueError):
        LiteralTime._parse_value('00:00+00:00')
    # Output: error
    with pytest.raises(AssertionError):
        LiteralTime._serialize(datetime.time(tzinfo=pytz.UTC))  # fails even on UTC. Has to be naive


    # === LiteralDateTime
    assert LiteralDateTime._parse_value('2022-12-31 23:59') == d_23_59
    assert LiteralDateTime._serialize(d_23_59) == '2022-12-31 23:59:00'

    # Aware times
    # Input: error
    with pytest.raises(ValueError):
        LiteralDateTime._parse_value('2022-01-01 00:00+00:00')
    # Output: error
    with pytest.raises(AssertionError):
        LiteralDateTime._serialize(d_23_59.replace(tzinfo=pytz.utc))

    # === DateTimeWithTimezone
    d_23_59_moscow = d_23_59.replace(tzinfo=moscow)
    assert DateTimeWithTimezone._parse_value('2022-12-31 23:59:00+02:00') == d_23_59_moscow
    assert DateTimeWithTimezone._serialize(d_23_59_moscow) == '2022-12-31 23:59:00+02:00'

