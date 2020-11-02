from typing import Optional, Any

import yaml  # optional dependency; this module is only usable when it's installed
from fastapi import Query

from apiens.views.mongoquery_crud import QueryObject, ModernQueryObject


def query_object(*,
        select: Optional[str] = Query(
            None,
            title='The list of fields to select.',
            description='Example: `[id, login]` or `{ id: 1, login: 1, tenant: { id: 1 }}`. JSON or YAML.',
        ),
        filter: Optional[str] = Query(
            None,
            title='Filter criteria.',
            description='MongoDB format. Example: `{ age: { $gt: 18 } }`. JSON or YAML.'
        ),
        sort: Optional[str] = Query(
            None,
            title='Sorting order',
            description='List of columns with `+` or `-`. Example: `[ login, ctime- ]`. JSON or YAML.',
        ),
        skip: Optional[int] = Query(
            None,
            title='Pagination. The number of items to skip.'
        ),
        limit: Optional[int] = Query(
            None,
            title='Pagination. The number of items to include.'
        ),
) -> Optional[QueryObject]:
    """ Get the MongoSql Query Object from the request

    Raises:
        ArgumentValueError
    """
    # Empty?
    if not select and not filter and not sort and not skip and not limit:
        return None

    # Parse
    query_object = ModernQueryObject(
        select=_parse_yaml_argument('select', select),
        filter=_parse_yaml_argument('filter', filter),
        sort=_parse_yaml_argument('sort', sort),
        skip=skip,
        limit=limit,
    )

    # Convert
    return convert_query_object_to_old(query_object)


class ArgumentValueError(ValueError):
    """ Query object field parse error """
    def __init__(self, argument_name: str, error: str):
        self.argument_name = argument_name
        super().__init__(error)


def _parse_yaml_argument(name: str, value: Optional[str]) -> Any:
    """ Parse a flattened QueryObject field """
    # None passthrough
    if value is None:
        return None

    # Parse the string
    try:
        return yaml.load(value, Loader=yaml.SafeLoader)
    except yaml.YAMLError as e:
        raise ArgumentValueError(name, str(e))


def convert_query_object_to_old(query_object: ModernQueryObject) -> QueryObject:
    """ Convert a Query Object from the new format into the old format

    Two differences:
    * `project` is now called `select`
    * `join` and `joinf` are deprecated and aren't expected to be used
    """
    query_object = query_object.copy()

    # Rename 'select' to 'project'
    if 'select' in query_object:
        project = query_object['project'] = query_object.pop('select')

        # Convert mixed projection into dict projection
        if isinstance(project, list) and any(isinstance(v, dict) for v in project):
            # List projections support one mixed syntax: [name, name, {name: {...}}]
            query_object['project'] = {name: 1 for name in project if isinstance(name, str)}
            for value in project:
                if isinstance(value, dict):
                    query_object['project'].update(value)

        # Convert nested queries
        project = query_object['project']
        if isinstance(project, dict):
            for name, value in project.items():
                if isinstance(value, dict):
                    project[name] = convert_query_object_to_old(value)

    return query_object


def unconvert_query_object_from_old(query_object: QueryObject) -> ModernQueryObject:
    query_object = query_object.copy()
    if 'project' in query_object:
        query_object['select'] = query_object.pop('project')
    return query_object
