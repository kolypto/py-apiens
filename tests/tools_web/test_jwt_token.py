from __future__ import annotations

import pytest
import pydantic as pd
import platform
from datetime import datetime, timedelta


@pytest.mark.skipif(pd.VERSION == '1.7.4', reason="""
    Fails with Pydantic 1.7.4: says, APIAccessToken has no attribute 'SECRET_KEY'.
    Looks like this version has some issues with class-level attributes.
""")
@pytest.mark.skipif(platform.python_version() == '3.10.6' and pd.VERSION in ('1.7.4', '1.8', '1.8.1', '1.8.2'), reason="""
    Fails with newer Python 3.10 versions and older Pydantic versions: "
    complains that "ClassVar" is not a valid field annotation. That's a bug in Python.
""")
def test_jwt_token():
    print(repr(platform.python_version()))
    from apiens.tools.web.jwt_token import StructuredJWTToken, looks_like_jwt_token

    def main():
        # === Test: token with expiration
        d7 = timedelta(days=7)

        # Create a token
        session_id = '1234'
        token = APIAccessToken.create(
            {'id': session_id}, 
            expires_in=d7
        )

        now = datetime.utcnow()
        now_plus_7 = now + d7

        # Check it
        assert token.sub.id == session_id
        assert token.exp.timestamp() == pytest.approx(now_plus_7.timestamp(), abs=60)
        assert token.expires_in.total_seconds() == pytest.approx(d7.total_seconds(), abs=60)

        # Encode, Decode
        token_str = token.encode()
        assert looks_like_jwt_token(token_str)
        token = APIAccessToken.decode(token_str)

        # Check decoded
        assert token.sub.id == session_id
        assert token.exp.timestamp() == pytest.approx(now_plus_7.timestamp(), abs=60)
        assert token.expires_in.total_seconds() == pytest.approx(d7.total_seconds(), abs=60)

        # === Test: token without expiration
        with pytest.raises(AssertionError):
            APIAccessToken.create({'id': session_id}, expires_in=None)


    class SessionInfo(pd.BaseModel):
        id: str
    
    class APIAccessToken(StructuredJWTToken):
        SECRET_KEY = 'abcdef'
        sub: SessionInfo
    
    APIAccessToken.update_forward_refs(**locals())
    

    # Go
    main()
    
    