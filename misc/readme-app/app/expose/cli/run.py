import typer

app = typer.Typer(
    help='Run application',
    no_args_is_help=True,
)


@app.command()
def uvicorn(host: str = '0.0.0.0', port: int = 5000):
    """ Run the application """
    import uvicorn
    from app.globals.config import settings

    # Alternatively:
    # $ uvicorn module:app --reload

    uvicorn.run(
        'app.expose.fastapi.app:asgi_app',
        host=host,
        port=port,
        debug=not settings.is_production,
        reload=not settings.is_production,
        reload_dirs=[
            # Only watch specific directories. We have too many files in CWD
            'misc',
        ],
    )
