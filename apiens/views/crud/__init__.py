""" Class-based views for Create, Read, Update, Delete operations """

from . import crud_signals
from .crudbase import SimpleCrudBase, CrudBase
from .crudbase import saves_custom_fields
from .crud_settings import CrudSettings
from .crud_settings_mongosql import MongoSqlCrudSetttings
from .instance_history_proxy import InstanceHistoryProxy, get_history_proxy_for_instance
from .pg_integrity_error import extract_postgres_unique_violation_columns
