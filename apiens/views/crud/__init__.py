""" Class-based views for Create, Read, Update, Delete operations """

from . import crud_signals
from .defs import AUTOMATIC, InstanceDict, UserFilterValue
from .crudbase import SimpleCrudBase, CrudBase
from .crudbase import saves_custom_fields
from .crud_settings import CrudSettings
from .instance_history_proxy import InstanceHistoryProxy, get_history_proxy_for_instance

try:
    from .pg_integrity_error import extract_postgres_unique_violation_columns
except ImportError as e:
    if e.name != 'psycopg2':
        raise
