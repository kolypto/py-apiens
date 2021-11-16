from .mutate_api import MutateApi
from ..query.query_api import QueryApi


class ReturningMutateApi(MutateApi, QueryApi):
    def create(self, user: dict) -> dict:
        id = super().create(user)
        # TODO: implement!
        return {'id': id, 'is_admin': True, 'login': 'kolypto', 'name': 'Mark'}

    def update(self, user: dict) -> dict:
        id = super().update(user)
        # TODO: implement!
        return {'id': id, 'is_admin': True, 'login': 'kolypto', 'name': 'Mark', **user}

    def update_id(self, id: int, user: dict) -> dict:
        id = super().update_id(id, user)
        # TODO: implement!
        return {'id': id, 'is_admin': True, 'login': 'kolypto', 'name': 'Mark', **user}

    def delete(self, id: int) -> dict:
        id = super().delete(id)
        # TODO: implement!
        return {'id': id, 'is_admin': True, 'login': 'kolypto', 'name': 'Mark'}
