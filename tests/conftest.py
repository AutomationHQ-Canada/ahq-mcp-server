import base64
import json
import os


def _fake_jwt(claims: dict) -> str:
    # org_id is derived by decoding the token's own payload (see AhqCredentials.from_settings) —
    # tests need a real JWT-shaped (if unsigned) token so that decode succeeds, not an arbitrary string.
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"eyJhbGciOiJub25lIn0.{payload}.fake-signature"


os.environ.setdefault("AHQ_BASE_URL", "https://api-dev.automationhq.ai")
os.environ.setdefault("AHQ_API_TOKEN", _fake_jwt({"organizationId": "test-org", "organizationName": "Test Org", "tokenType": "ORGANIZATION"}))
os.environ.setdefault("AHQ_PROJECT_ID", "test-project")
