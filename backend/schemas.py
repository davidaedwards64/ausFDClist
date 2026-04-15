from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    model: str
    php_api_base_url: str


class AuthConfigResponse(BaseModel):
    okta_client_id: str
    okta_issuer: str
    okta_domain: str
    okta_redirect_uri: str
