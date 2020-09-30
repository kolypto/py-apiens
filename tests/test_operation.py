from __future__ import annotations

from dataclasses import dataclass

from typing import Optional, Any

from apiens import di, operation


def test_operations():
    """ Test a few operations """

    def main():
        # Try out @operation-decorated business logic with an Injector DI
        with di.Injector() as root:
            root.provide(authenticated_user, authenticated_user)

            # Call some operations
            assert call_operation(root, 'whoami') == 'kolypto'
            assert call_operation(root, 'list_users') == []
            assert call_operation(root, 'create_user', login='ootync') == None
            assert call_operation(root, 'list_users') == [User(login='ootync', created_by=User(login='kolypto'))]
            assert call_operation(root, 'delete_user', index=0) == None
            assert call_operation(root, 'list_users') == []

    # Example dependency
    @di.signature()
    def authenticated_user():
        return User(login='kolypto')

    # Example operation
    @operation()
    @di.kwargs(current_user=authenticated_user)
    def whoami(current_user: User):
        return current_user.login

    users = []

    # Example CRUD operations
    @operation()
    @di.kwargs(current_user=authenticated_user)
    def create_user(current_user: User, login: str):
        users.append(User(login=login, created_by=current_user))

    @operation()
    @di.kwargs()
    def list_users():
        return users

    @operation()
    @di.kwargs()
    def delete_user(index: int):
        del users[index]

    # Example router
    all_operations = [whoami, create_user, list_users, delete_user]

    operations_map = {
        # Operation id mapped to operation func
        operation.get_from(op).operation_id: op
        for op in all_operations
    }

    def call_operation(injector: di.Injector, operation_name: str, **kwargs):
        operation_func = operations_map[operation_name]  # might as well check the arguments here
        return injector.invoke(operation_func, **kwargs)

    # Test
    main()


def test_class_based_operation():
    """ Test operations defined as a class """

    def main():
        # Try out @operation-decorated business logic with an Injector DI and class-based CRUD
        with di.Injector() as root:
            root.provide(authenticated_user, authenticated_user)

            # Call some operations
            assert call_operation(root, 'whoami') == 'kolypto'
            assert call_operation(root, 'user/list') == []
            assert call_operation(root, 'user/create', login='ootync') == None
            assert call_operation(root, 'user/list') == [User(login='ootync', created_by=User(login='kolypto'))]
            assert call_operation(root, 'user/delete', index=0) == None
            assert call_operation(root, 'user/list') == []

    # Example dependency
    @di.signature()
    def authenticated_user():
        return User(login='kolypto')

    # Example flat operation
    @operation()
    @di.kwargs(current_user=authenticated_user)
    def whoami(current_user: User):
        return current_user.login

    # Example class-based CRUD
    @operation('user')
    @di.kwargs(current_user=authenticated_user)
    class UserCrud:
        _db = []

        def __init__(self, current_user):
            self.current_user = current_user

        @operation()
        @di.signature()
        def list(self):
            return self._db

        @operation()
        @di.signature()
        def create(self, login: str):
            self._db.append(User(login=login, created_by=self.current_user))

        @operation()
        @di.signature()
        def delete(self, index: int):
            del self._db[index]

    # Example router
    flat_operations = [whoami]
    class_based_operations = [UserCrud]

    flat_operations_map = {
        # Flat operations are trivial
        operation.get_from(op).operation_id: op
        for op in flat_operations
    }

    class_based_operations_map = {
        # Class-based operations are not
        operation.get_from(UserCrud).operation_id + '/' + op.operation_id: (cls, op.func_name)
        for cls in class_based_operations
        for op in operation.all_decorated_from(cls)
    }

    def call_operation(injector: di.Injector, operation_name: str, **kwargs):
        # Flat operations. Go straight ahead
        if operation_name in flat_operations_map:
            operation_func = flat_operations_map[operation_name]
            return injector.invoke(operation_func, **kwargs)
        # Class-based operations
        elif operation_name in class_based_operations_map:
            cls, method_name = class_based_operations_map[operation_name]

            # Construct, invoke
            obj = injector.invoke(cls)
            return injector.invoke(
                getattr(obj, method_name),
                **kwargs
            )

    # Test
    main()


def test_operation_signature():
    """ Test how signature reading works """

    # An operation with pure arguments, no DI involved

    @operation()
    def f(a, b: int, c=1, d: int = 2) -> str:
        pass

    s = operation.get_from(f).signature
    assert s.provided_arguments == {}
    assert s.arguments == {'a': Any, 'b': int, 'c': Any, 'd': int}
    assert s.argument_defaults == {'c': 1, 'd': 2}
    assert s.return_type == str

    # An operation with DI.
    # Argument 'c' goes into the "provided" list and leaves all other lists.

    @operation()
    @di.kwargs(c='something')
    def f(a, b: int, c=1, d: int = 2) -> str:
        pass

    s = operation.get_from(f).signature
    assert s.provided_arguments == {'c': Any}  # provided. 'c' is removed from all other lists
    assert s.arguments == {'a': Any, 'b': int, 'd': int}
    assert s.argument_defaults == {'d': 2}
    assert s.return_type == str


@dataclass
class User:
    login: str
    created_by: Optional[User] = None
