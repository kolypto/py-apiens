import fastapi
from app import exc


router = fastapi.APIRouter()

@router.get('/unexpected_error')
def view_unexpected_error():
    raise RuntimeError('Fail')


@router.get('/app_error')
def view_app_error():
    raise exc.E_NOT_FOUND(
        # Error: the negative message
        "User not found by email",
        # Fixit: the positive message
        "Please check the provided email",
        # additional information
        object='User',
        email='user@example.com',
    )