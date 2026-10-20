from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from app.application.service import ResearchService
from app.application.agent import ResearchAgent
from app.domain.models import Role
from app.infrastructure.repository import ResearchRepository
from app.infrastructure.llm import LLMClient
from app.interfaces import (
    ChatRequest,
    LoginRequest,
    ResearchCreateRequest,
    current_user,
    hash_password,
    require_role,
    verify_password,
)


def build_app(db_path: str | None = None) -> FastAPI:
    repo = ResearchRepository(
        db_path or os.getenv("DATABASE_SQLITE_PATH", "backend/.data/research.db")
    )
    repo.seed_users(
        [
            {
                "id": "u-admin",
                "email": "admin@example.com",
                "password_hash": hash_password("Admin123!"),
                "tenant_id": "tenant-a",
                "role": Role.ADMIN.value,
            },
            {
                "id": "u-researcher",
                "email": "researcher@example.com",
                "password_hash": hash_password("Research123!"),
                "tenant_id": "tenant-a",
                "role": Role.RESEARCHER.value,
            },
            {
                "id": "u-viewer",
                "email": "viewer@example.com",
                "password_hash": hash_password("Viewer123!"),
                "tenant_id": "tenant-a",
                "role": Role.VIEWER.value,
            },
            {
                "id": "u-other",
                "email": "other@example.com",
                "password_hash": hash_password("Other123!"),
                "tenant_id": "tenant-b",
                "role": Role.RESEARCHER.value,
            },
        ]
    )
    service = ResearchService(repo)
    llm = LLMClient()
    agent = ResearchAgent(llm)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield

    app = FastAPI(title="跨境电商选品调研 Agent", version="0.1.0", lifespan=lifespan)
    app.state.repo = repo
    app.state.service = service
    allowed_origins = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if origin.strip()
    ]
    is_production = os.getenv("APP_ENV", "development").lower() == "production"
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        # Local development may use 3000, 3001, or a temporary Next port.
        # Keep this regex disabled in production so deployment stays allowlist-only.
        allow_origin_regex=(
            None if is_production else r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "service": "research-api", "version": app.version}

    @app.post("/api/v1/auth/login")
    def login(body: LoginRequest):
        user = repo.user_by_email(body.email.lower().strip())
        if not user or not verify_password(body.password, user["password_hash"]):
            raise HTTPException(
                status_code=401,
                detail={"code": "INVALID_CREDENTIALS", "message": "邮箱或密码错误"},
            )
        from app.interfaces import issue_token

        return {
            "request_id": request_id(),
            "access_token": issue_token(user),
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "email": user["email"],
                "tenant_id": user["tenant_id"],
                "role": user["role"],
            },
        }

    @app.post("/api/v1/research-runs", status_code=202)
    def create_run(
        body: ResearchCreateRequest,
        user=Depends(require_role(Role.ADMIN, Role.RESEARCHER)),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ):
        run = service.create(
            tenant_id=user["tenant_id"],
            user_id=user["sub"],
            input_data=body.model_dump(),
            idempotency_key=idempotency_key,
        )
        return {
            "request_id": request_id(),
            "run_id": run["id"],
            "status": run["status"],
        }

    @app.get("/api/v1/research-runs/{run_id}")
    def get_run(run_id: str, user=Depends(current_user)):
        run = service.get(run_id, user["tenant_id"])
        if not run:
            raise HTTPException(
                status_code=404,
                detail={"code": "RUN_NOT_FOUND", "message": "任务不存在"},
            )
        return {"request_id": request_id(), **run}

    @app.post("/api/v1/research-runs/{run_id}/retry")
    def retry_run(run_id: str, user=Depends(require_role(Role.ADMIN, Role.RESEARCHER))):
        try:
            return {
                "request_id": request_id(),
                **service.retry(run_id, user["tenant_id"]),
            }
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail={"code": "RUN_NOT_FOUND", "message": "任务不存在"},
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=409, detail={"code": "INVALID_STATE", "message": str(exc)}
            )

    @app.post("/api/v1/research-runs/{run_id}/cancel")
    def cancel_run(
        run_id: str, user=Depends(require_role(Role.ADMIN, Role.RESEARCHER))
    ):
        try:
            return {
                "request_id": request_id(),
                **service.cancel(run_id, user["tenant_id"]),
            }
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail={"code": "RUN_NOT_FOUND", "message": "任务不存在"},
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=409, detail={"code": "INVALID_STATE", "message": str(exc)}
            )

    @app.get("/api/v1/research-runs/{run_id}/events")
    def events(run_id: str, user=Depends(current_user)):
        run = service.get(run_id, user["tenant_id"])
        if not run:
            raise HTTPException(
                status_code=404,
                detail={"code": "RUN_NOT_FOUND", "message": "任务不存在"},
            )
        payload = json.dumps(
            {"run_id": run_id, "status": run["status"], "nodes": run["nodes"]},
            ensure_ascii=False,
        )
        return StreamingResponse(
            iter([f"event: progress\ndata: {payload}\n\n"]),
            media_type="text/event-stream",
        )

    @app.get("/api/v1/research-runs/{run_id}/report")
    def report(
        run_id: str,
        format: str = Query(default="json", pattern="^(json|csv)$"),
        user=Depends(current_user),
    ):
        try:
            if format == "csv":
                return Response(
                    content=service.export_csv(run_id, user["tenant_id"]),
                    media_type="text/csv",
                    headers={
                        "Content-Disposition": f"attachment; filename={run_id}.csv"
                    },
                )
            report_data = repo.get_report(run_id, user["tenant_id"])
            if not report_data:
                raise KeyError
            return {"request_id": request_id(), "report": report_data}
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "REPORT_NOT_READY",
                    "message": "报告尚未生成或任务不存在",
                },
            )

    @app.get("/api/v1/research-runs/{run_id}/evidence")
    def evidence(run_id: str, user=Depends(current_user)):
        if not service.get(run_id, user["tenant_id"]):
            raise HTTPException(
                status_code=404,
                detail={"code": "RUN_NOT_FOUND", "message": "任务不存在"},
            )
        return {
            "request_id": request_id(),
            "items": repo.get_evidence(run_id, user["tenant_id"]),
        }

    @app.post("/api/v1/research-runs/{run_id}/chat")
    def chat(run_id: str, body: ChatRequest, user=Depends(current_user)):
        report_data = repo.get_report(run_id, user["tenant_id"])
        if not report_data:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "REPORT_NOT_READY",
                    "message": "报告生成后才能开始问答",
                },
            )
        agent_answer = agent.answer(body.question, report_data)
        if not agent_answer:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "AGENT_UNAVAILABLE",
                    "message": "智能助理暂时无法完成工具问答，请检查模型服务配置后重试。",
                },
            )
        return {
            "request_id": request_id(),
            **agent_answer,
            "data_version": report_data["traceability"]["source_version"],
        }

    return app


def request_id() -> str:
    import secrets

    return secrets.token_hex(8)


app = build_app()
