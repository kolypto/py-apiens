import nox.sessions

# Nox
nox.options.reuse_existing_virtualenvs = True
nox.options.sessions = [
    'tests',
    'tests_sqlalchemy',
    'tests_fastapi',
    'tests_ariadne',
    'tests_pydantic',
]

# Versions
PYTHON_VERSIONS = ['3.9', '3.10']
SQLALCHEMY_VERSIONS = [
    # Selective
    '1.3.11', '1.3.24',
    '1.4.23', '1.4.36',
]
FASTAPI_VERSIONS = [
    # Selective: one latest version from 0.5x, 0.6x, 0.7x and so on
    '0.59.0', '0.69.0', '0.73.0', '0.75.0', '0.78.0',
]
ARIADNE_VERSIONS = [
    # Selective
    '0.13.0', '0.14.1', '0.15.1',
]
GRAPHQL_CORE_VERSIONS = [
    '3.1.0', '3.1.1', '3.1.2', '3.1.3', '3.1.4', '3.1.5', '3.1.6', '3.1.7',
    '3.2.0', '3.2.1',
]
PYDANTIC_VERSIONS = [
    # Selective
    '1.7.4',  # latest 1.7.x
    '1.8', '1.8.1', '1.8.2',
    '1.9.0', '1.9.1',
]


@nox.session(python=PYTHON_VERSIONS)
def tests(session: nox.sessions.Session, *, overrides: dict[str, str] = {}):
    """ Run all tests """
    # This approach works ok on GitHub but fails locally because we have Poetry within Poetry
    # session.install('poetry')
    # session.run('poetry', 'install')

    # This approach works better locally: install from requirements.txt
    session.install(*requirements_txt, '.')

    if overrides:
        session.install(*(f'{name}=={version}' for name, version in overrides.items()))

    # Test
    args = ['-k', 'not extra']
    if not overrides:
        args.append('--cov=apiens')

    session.run('pytest', 'tests/', *args)


@nox.session(python=PYTHON_VERSIONS[-1])
@nox.parametrize('sqlalchemy', SQLALCHEMY_VERSIONS)
def tests_sqlalchemy(session: nox.sessions.Session, sqlalchemy):
    """ Test against a specific SqlAlchemy version """
    tests(session, overrides={'sqlalchemy': sqlalchemy})


@nox.session(python=PYTHON_VERSIONS[-1])
@nox.parametrize('fastapi', FASTAPI_VERSIONS)
def tests_fastapi(session: nox.sessions.Session, fastapi):
    """ Test against a specific FastAPI version """
    tests(session, overrides={'fastapi': fastapi})


@nox.session(python=PYTHON_VERSIONS[-1])
@nox.parametrize('ariadne', ARIADNE_VERSIONS)
def tests_ariadne(session: nox.sessions.Session, ariadne):
    """ Test against a specific Ariadne version """
    tests(session, overrides={'ariadne': ariadne})


@nox.session(python=PYTHON_VERSIONS[-1])
@nox.parametrize('graphql_core', GRAPHQL_CORE_VERSIONS)
def tests_graphql(session: nox.sessions.Session, graphql_core):
    """ Test against a specific GraphQL version """
    tests(session, overrides={'graphql-core': graphql_core})


@nox.session(python=PYTHON_VERSIONS[-1])
@nox.parametrize('pydantic', PYDANTIC_VERSIONS)
def tests_pydantic(session: nox.sessions.Session, pydantic):
    """ Test against a specific Pydantic version """
    tests(session, overrides={'pydantic': pydantic})


# Get requirements.txt from external poetry
import tempfile, subprocess
with tempfile.NamedTemporaryFile('w+') as f:
    subprocess.run(f'poetry export --no-interaction --dev --format requirements.txt --without-hashes --output={f.name}', shell=True, check=True)
    f.seek(0)
    requirements_txt = [line.split(';', 1)[0] for line in f.readlines()]  # after ";" go some Python version specifiers
