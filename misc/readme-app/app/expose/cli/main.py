import typer 
from importlib import import_module

app = typer.Typer(no_args_is_help=True)

app.add_typer(import_module('app.expose.cli.run').app, name='run')

if __name__ == '__main__':
    app()
