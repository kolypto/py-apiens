from typing import TypeVar, Any


# Values for an instance's Primary Key dict
PrimaryKeyDict = dict[str, Any]

# Values for an SqlAlchemy instance, in the form of a dictionary. Possibly, partial.
InstanceDict = dict[str, Any]


# User-supplied values for filtering objects
UserFilterValue = Any


# Sugar. Marks a field that will be automatically initialized.
AUTOMATIC = None
