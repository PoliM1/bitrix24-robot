import json
import os
import time
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

app = FastAPI(title="Bitrix24 Robot")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
TOKENS_FILE = DATA_DIR / "bitrix_tokens.json"


def load_tokens():
    if TOKENS_FILE.exists():
        with open(TOKENS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_tokens(data: dict):
    with open(TOKENS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_env(name: str, default: str | None = None):
    value = os.getenv(name, default)
    if value is None or value == "":
        raise HTTPException(status_code=500, detail=f"Не задана переменная окружения: {name}")
    return value


def get_domain():
    tokens = load_tokens()
    return tokens.get("domain") or os.getenv("BITRIX_DOMAIN")


def refresh_access_token():
    tokens = load_tokens()

    client_id = get_env("BITRIX_CLIENT_ID")
    client_secret = get_env("BITRIX_CLIENT_SECRET")
    refresh_token = tokens.get("refresh_token")
    domain = tokens.get("domain") or os.getenv("BITRIX_DOMAIN")

    if not refresh_token or not domain:
        raise HTTPException(status_code=400, detail="Нет refresh_token или domain. Сначала переустанови приложение в Bitrix24.")

    url = f"https://{domain}/oauth/token/"
    payload = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }

    response = requests.post(url, data=payload, timeout=30)
    data = response.json()

    if response.status_code != 200 or "access_token" not in data:
        raise HTTPException(status_code=400, detail={"refresh_error": data})

    new_tokens = {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", refresh_token),
        "domain": data.get("domain", domain),
        "expires_at": int(time.time()) + int(data.get("expires_in", 3600)) - 60,
        "member_id": data.get("member_id"),
        "scope": data.get("scope"),
    }
    save_tokens(new_tokens)
    return new_tokens


def get_valid_access_token():
    tokens = load_tokens()
    access_token = tokens.get("access_token")
    expires_at = tokens.get("expires_at", 0)

    if access_token and time.time() < expires_at:
        return access_token

    refreshed = refresh_access_token()
    return refreshed["access_token"]


@app.get("/health")
async def health():
    tokens = load_tokens()
    return {
        "status": "ok",
        "installed": bool(tokens.get("access_token")),
        "domain": tokens.get("domain") or os.getenv("BITRIX_DOMAIN"),
    }


@app.get("/bitrix/install")
async def bitrix_install(
    access_token: str | None = None,
    refresh_token: str | None = None,
    domain: str | None = None,
    expires_in: int = 3600,
    member_id: str | None = None,
    scope: str | None = None,
):
    if not access_token or not refresh_token or not domain:
        raise HTTPException(
            status_code=400,
            detail="Не хватает параметров: access_token, refresh_token, domain"
        )

    data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "domain": domain,
        "expires_at": int(time.time()) + int(expires_in) - 60,
        "member_id": member_id,
        "scope": scope,
    }
    save_tokens(data)

    return {
        "status": "install_ok",
        "domain": domain,
        "expires_at": data["expires_at"],
    }


@app.get("/bitrix/task/create")
async def create_task(
    title: str = Query(..., description="Название задачи"),
    responsible_id: int = Query(..., description="ID ответственного"),
    creator_id: int = Query(1, description="ID постановщика"),
    description: str = Query("", description="Описание задачи"),
):
    access_token = get_valid_access_token()
    domain = get_domain()

    if not domain:
        raise HTTPException(status_code=400, detail="Не задан domain Bitrix24")

    url = f"https://{domain}/rest/api/tasks.task.add"
    payload = {
        "fields": {
            "title": title,
            "description": description,
            "creatorId": creator_id,
            "responsibleId": responsible_id,
        },
        "auth": access_token,
    }

    response = requests.post(url, json=payload, timeout=30)
    data = response.json()

    if response.status_code != 200 or "result" not in data:
        raise HTTPException(status_code=400, detail={"bitrix_error": data})

    task_id = None
    result = data.get("result")

    if isinstance(result, dict):
        task = result.get("task")
        if isinstance(task, dict):
            task_id = task.get("id")
        if not task_id:
            task_id = result.get("id")
    elif isinstance(result, int):
        task_id = result

    return JSONResponse(
        content={
            "status": "task_created",
            "task_id": task_id,
            "bitrix_response": data,
        }
    )
