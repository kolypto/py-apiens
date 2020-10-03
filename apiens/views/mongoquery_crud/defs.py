from typing import Mapping, Union, TypedDict, List, Any


class QueryObject(TypedDict):
    """ MongoSQL Query Object """
    project: Union[str, List[str], Mapping[str, int]]
    filter: Mapping[str, Any]
    join: Mapping[str, Mapping]
    joinf: Mapping[str, Mapping]
    sort: Union[str, List[str]]
    group: Union[str, List[str]]
    skip: int
    limit: int
    count: int


class ModernQueryObject(TypedDict):
    """ Modern Query Object """
    select: Union[str, List[str], Mapping[str, Union[int, Mapping]]]
    filter: Mapping[str, Any]
    sort: Union[str, List[str]]
    skip: int
    limit: int
