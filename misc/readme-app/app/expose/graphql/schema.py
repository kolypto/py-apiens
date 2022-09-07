import ariadne

# Prepare definitions
from .query import Query
graphql_definitions: list[ariadne.SchemaBindable] = [
    Query,
]

# GraphQL schema
import os

import apiens.error.error_object
from apiens.tools.ariadne.schema.load import load_schema_from_module

app_schema = ariadne.make_executable_schema([
        # Load all *.graphql files from this folder
        ariadne.load_schema_from_path(os.path.dirname(__file__)),
        # Load a *.graphql file from a module
        load_schema_from_module(apiens.error.error_object, 'schema.graphql'),
    ],
    graphql_definitions,
    ariadne.snake_case_fallback_resolvers,
)

# Improve error messages from scalars like Int and Float
from apiens.tools.graphql.errors import human_readable
human_readable.install_types_to_schema(app_schema)
