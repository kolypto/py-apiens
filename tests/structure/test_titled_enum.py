from apiens.structure.titled_enum import TitledEnum, titled, get_title, get_description


def test_titled_enum():
    @titled('Message direction', description="The direction of a message")
    class Direction(TitledEnum):
        IN = -1, 'Incoming'
        OUT = +1, 'Outgoing'

    # Values have titles
    assert Direction.IN.value == -1
    assert Direction.IN.title == 'Incoming'

    # Enum itself has a title and a description
    assert get_title(Direction) == 'Message direction'
    assert get_description(Direction) == "The direction of a message"

    # Enum() and Enum[] are not broken
    assert Direction(-1) == Direction.IN
    assert Direction['IN'] == Direction.IN
