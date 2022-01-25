import nox.sessions

# Nox
nox.options.reuse_existing_virtualenvs = True
nox.options.sessions = [
    'tests',
    'tests_sqlalchemy',
    'tests_fastapi',
    'tests_ariadne',
]

# Versions
PYTHON_VERSIONS = ['3.9', '3.10']
SQLALCHEMY_VERSIONS = [
    # Selective
    '1.3.24', '1.4.23', '1.4.31',
]
FASTAPI_VERSIONS = [
    # Selective
    '0.59.0', '0.69.0', '0.73.0',
]
ARIADNE_VERSIONS = [
    # Selective
    '0.12.0', '0.13.0', '0.14.0',
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
        args.append('--cov=jessiql')

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


# Get requirements.txt from external poetry
import tempfile, subprocess
with tempfile.NamedTemporaryFile('w+') as f:
    subprocess.run(f'poetry export --no-interaction --dev --format requirements.txt --without-hashes --output={f.name}', shell=True, check=True)
    f.seek(0)
    requirements_txt = [line.split(';', 1)[0] for line in f.readlines()]  # after ";" go some Python version specifiers
