import graphql
import pytest

from jessiql.testing.graphql.query import graphql_query_sync
from apiens.tools.graphql import directives
from apiens.tools.graphql.resolver.resolve import resolves


def test_directive_partial():
    """ Test @partial """
    def main():
        # language=graphql
        partialUpdateUser = 'query ($user: UserInput) { partialUpdateUser(user: $user) { id login name age } }'

        # === Test: send a valid partial object
        res = graphql_query_sync(gql_schema, partialUpdateUser, user={
            'id': 1,
            'login': 'replaced',
            # nullable field is ok
            'age': None,
            # all other fields are skipped
        })
        assert res['partialUpdateUser'] == {
            'id': '1',
            'login': 'replaced',
            'name': 'John',
            'age': None,
        }

        # === Test: send an invalid partial object
        with pytest.raises(graphql.GraphQLError) as e:
            res = graphql_query_sync(gql_schema, partialUpdateUser, user={
                'id': 1,
                # non-nullable field cannot be null!
                'login': None,
                # all other fields are skipped
            })
        assert e.value.message == 'Fields must not be null: login'


    # language=graphql
    GQL_SCHEMA = '''
    input UserInput @partial {
        # This input object has all fields non-nullable, but actually, it will accept missing fields.
        # But when provided, these fields won't allow nulls!
        id: ID!
        login: String!
        name: String!
        age: Int
    }
    
    type Query {
        partialUpdateUser(user: UserInput): User!
    }

    type User {
        id: ID
        login: String
        name: String
        age: Int
    }
    '''
    GQL_SCHEMA += directives.partial.DIRECTIVE_SDL

    gql_schema = graphql.build_schema(GQL_SCHEMA)
    directives.partial.install_directive_to_schema(gql_schema)

    @resolves(gql_schema, 'Query', 'partialUpdateUser')
    def resolve_partial_update_user(root, info: graphql.GraphQLResolveInfo, user: dict):
        return {
            'id': '1',
            'login': 'original',
            'name': 'John',
            'age': 34,
            # Override
            **user,
        }

    main()


def test_directive_inherits():
    def main():
        # language=graphql
        getUser  = 'query ($user: UserLoginNameInput) { passthruUser(user: $user) { id login name } }'
        getUser1 = 'query ($user: User1Input) { passthruUser1(user: $user) { id name } }'
        getUser2 = 'query ($user: User2Input) { passthruUser2(user: $user) { id name } }'

        # === Test: input a model that inherits
        res = graphql_query_sync(gql_schema, getUser, user={'id': '1', 'login': 'qwerty', 'name': 'John'})
        assert res == {'passthruUser': {'id': '1', 'login': 'qwerty', 'name': 'John'}}

        # === Test: user1 and user2
        res = graphql_query_sync(gql_schema, getUser1, user={'id': '1', 'name': 'John'})
        assert res == {'passthruUser1': {'id': '1', 'name': 'John'}}

        res = graphql_query_sync(gql_schema, getUser2, user={'id': '1', 'name': 'John'})
        assert res == {'passthruUser2': {'id': '1', 'name': 'John'}}


    # language=graphql
    GQL_SCHEMA = '''
    type Query {
        # Note: 
        # Input object itself has only 1 field, 2 more are inherited
        # Same for the output object
        # So any extra field would fail or be rejected 
        passthruUser(user: UserLoginNameInput): UserLoginName
        
        # Test types that inherit 1) input from type 2) type from input
        passthruUser1(user: User1Input): User1
        passthruUser2(user: User2Input): User2
    }
    
    
    type User {
        id: ID!
    }
    type UserLogin @inherits(type: "User") {
        login: String!
    }
    type UserLoginName @inherits(type: "UserLogin") {
        name: String!
    }
    
    input UserInput {
        id: ID!
    }
    input UserLoginInput @inherits(type: "UserInput") {
        login: String!
    }
    input UserLoginNameInput @inherits(type: "UserLoginInput") {
        name: String!
    }
    
    
    # inherit from `type` to `input`
    type User1Base {
        name: String!
    }
    type User1 @inherits(type: "User1Base") {
        id: ID!
    }
    input User1Input @inherits(type: "User1Base") {
        id: ID
    }
    
    
    # inherit from `input` to `type`
    type User2Base {
        name: String!
    }
    type User2 @inherits(type: "User2Base") {
        id: ID!
    }
    input User2Input @inherits(type: "User2Base") {
        id: ID
    }
    '''
    GQL_SCHEMA += directives.inherits.DIRECTIVE_SDL

    gql_schema = graphql.build_schema(GQL_SCHEMA)
    directives.inherits.install_directive_to_schema(gql_schema)

    @resolves(gql_schema, 'Query', 'passthruUser')
    @resolves(gql_schema, 'Query', 'passthruUser1')
    @resolves(gql_schema, 'Query', 'passthruUser2')
    def resolve_passhru_user(root, info: graphql.GraphQLResolveInfo, user: dict):
        return user

    main()
