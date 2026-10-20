from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.models import Role
from app.infrastructure.repository import ResearchRepository


# In local tests a process-random secret is sufficient; deployments must inject JWT_SECRET.
JWT_SECRET = os.getenv("JWT_SECRET") or secrets.token_urlsafe(32)


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return base64.urlsafe_b64encode(salt + digest).decode()


def verify_password(password: str, encoded: str) -> bool:
    try:
        raw = base64.urlsafe_b64decode(encoded.encode())
        return hmac.compare_digest(hash_password(password, raw[:16]), encoded)
    except (ValueError, IndexError):
        return False


def issue_token(user: dict[str, Any]) -> str:
    payload = {"sub": user["id"], "email": user["email"], "tenant_id": user["tenant_id"], "role": user["role"], "exp": int(time.time()) + 8 * 3600}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(JWT_SECRET.encode(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"


def parse_token(token: str) -> dict[str, Any]:
    try:
        body, signature = token.split(".", 1)
        expected = hmac.new(JWT_SECRET.encode(), body.encode(), hashlib.sha256).digest()
        actual = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
        if not hmac.compare_digest(actual, expected):
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if int(payload["exp"]) < int(time.time()):
            raise ValueError
        return payload
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"code": "INVALID_TOKEN", "message": "登录状态无效或已过期"})


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)


class ResearchCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keyword: str = Field(min_length=1, max_length=100)
    market: str = Field(default="US", min_length=2, max_length=2)
    price_min: float | None = Field(default=None, gt=0)
    price_max: float | None = Field(default=None, gt=0)
    target_margin: float | None = Field(default=None, ge=0, le=1)
    supply_requirements: str | None = Field(default=None, max_length=500)
    shipping_method: str = Field(default="sea", pattern="^(sea|air|platform|self_fulfilled)$")
    ad_rate: float | None = Field(default=None, ge=0, le=1)
    return_rate: float | None = Field(default=None, ge=0, le=1)
    depth: str = Field(default="standard", pattern="^(standard|enhanced)$")

    @field_validator("keyword")
    @classmethod
    def keyword_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("keyword 不能为空")
        return value.strip()

    @field_validator("market")
    @classmethod
    def supported_market(cls, value: str) -> str:
        value = value.upper()
        if value != "US":
            raise ValueError("第一阶段仅支持 US 市场")
        return value

    @model_validator(mode="after")
    def valid_range(self) -> "ResearchCreateRequest":
        if self.price_min is not None and self.price_max is not None and self.price_min > self.price_max:
            raise ValueError("最低价格不能高于最高价格")
        return self


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("问题不能为空")
        return value.strip()


def current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "请先登录"})
    return parse_token(authorization.removeprefix("Bearer ").strip())


def require_role(*roles: Role):
    def dependency(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        if user.get("role") not in {role.value for role in roles}:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "当前角色无权执行此操作"})
        return user
    return dependency


def request_id_header() -> str:
    return secrets.token_hex(8)
