import json
import os
import time
from pathlib import Path
from urllib.parse import parse_qs

import requests
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Bitrix24 Robot")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
TOKENS_FILE = DATA_DIR / "bitrix_tokens.json"
DEBUG_FILE = DATA_DIR / "last_install_debug.json"


def load_tokens():
    if TOKENS_FILE.exists():
        with open(TOKENS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_tokens(data: dict):
    with open(TOKENS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_domain():
    tokens = load_tokens()
    return tokens.get("domain") or os.getenv("BITRIX_DOMAIN")


def extract_install_payload(payload: dict):
    # Берем данные из auth блока Bitrix24
    auth = payload.get("auth", {})
    
    access_token = auth.get("access_token")
    refresh_token = auth.get("refresh_token") 
    domain = auth.get("domain")
    expires_in = auth.get("expires_in", 3600)
    member_id = auth.get("member_id")
    scope = auth.get("scope")
    user_id = auth.get("user_id")

    try:
        expires_in = int(expires_in)
    except:
        expires_in = 3600

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "domain": domain,
        "expires_in": expires_in,
        "member_id": member_id,
        "scope": scope,
        "user_id": user_id,
    }


def refresh_access_token():
    tokens = load_tokens()
    client_id = os.getenv("BITRIX_CLIENT_ID")
    client_secret = os.getenv("BITRIX_CLIENT_SECRET")
    refresh_token = tokens.get("refresh_token")
    domain = tokens.get("domain")

    if not all([client_id, client_secret, refresh_token, domain]):
        raise HTTPException(status_code=400, detail="Недостаточно данных для обновления токена")

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
        "domain": domain,
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

    return refresh_access_token()["access_token"]


@app.get("/health")
async def health():
    tokens = load_tokens()
    return {
        "status": "ok",
        "installed": bool(tokens.get("access_token")),
        "domain": tokens.get("domain") or os.getenv("BITRIX_DOMAIN"),
    }


@app.get("/debug/install")
async def debug_install():
    if DEBUG_FILE.exists():
        with open(DEBUG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"status": "no_debug_data"}


@app.api_route("/bitrix/install", methods=["GET", "POST"])
async def bitrix_install(request: Request):
    payload = {}
    payload.update(dict(request.query_params))

    raw_body = await request.body()
    raw_body_text = raw_body.decode("utf-8", errors="replace")
    
    if raw_body_text and "application/x-www-form-urlencoded" in request.headers.get("content-type", ""):
        parsed_form = parse_qs(raw_body_text, keep_blank_values=True)
        # Распаковываем вложенные auth[ключ]=значение
        auth_data = {}
        for key, value in parsed_form.items():
            if key.startswith("auth[") and key.endswith("]"):
                inner_key = key[5:-1]  # убираем auth[] 
                auth_data[inner_key] = value[0] if value else ""
        payload["auth"] = auth_data

    data = extract_install_payload(payload)

    # Проверяем наличие обязательных токенов
    if not all([data["access_token"], data["refresh_token"], data["domain"]]):
        return JSONResponse(
            status_code=400,
            content={
                "detail": "Токены не найдены в запросе",
                "auth_data": payload.get("auth", {}),
                "extracted": data
            },
        )

    # СОХРАНЯЕМ ТОКЕНЫ!
    tokens_to_save = {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "domain": data["domain"],
        "expires_at": int(time.time()) + int(data["expires_in"]) - 60,
        "member_id": data["member_id"],
        "scope": data["scope"],
        "user_id": data["user_id"],
    }
    save_tokens(tokens_to_save)

    return {
        "status": "install_ok ✅",
        "domain": data["domain"],
        "member_id": data["member_id"],
        "scope": data["scope"],
        "expires_at": tokens_to_save["expires_at"],
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

    task_id = data["result"].get("task", {}).get("id") or data["result"].get("id")

    return {
        "status": "task_created ✅",
        "task_id": task_id,
        "bitrix_response": data,
    }
