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


def save_debug(data: dict):
    with open(DEBUG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_env(name: str, default: str | None = None):
    value = os.getenv(name, default)
    if value is None or value == "":
        raise HTTPException(status_code=500, detail=f"Не задана переменная окружения: {name}")
    return value


def get_domain():
    tokens = load_tokens()
    return tokens.get("domain") or os.getenv("BITRIX_DOMAIN")


def flatten_qs_dict(data: dict):
    flat = {}
    for k, v in data.items():
        if isinstance(v, list):
            flat[k] = v[0] if v else ""
        else:
            flat[k] = v
    return flat


def extract_install_payload(payload: dict):
    auth = payload.get("auth", {}) if isinstance(payload.get("auth"), dict) else {}

    access_token = (
        payload.get("access_token")
        or payload.get("AUTH_ID")
        or auth.get("access_token")
    )
    refresh_token = (
        payload.get("refresh_token")
        or payload.get("REFRESH_ID")
        or auth.get("refresh_token")
    )
    domain = (
        payload.get("domain")
        or payload.get("DOMAIN")
        or auth.get("domain")
        or os.getenv("BITRIX_DOMAIN")
    )
    expires_in = (
        payload.get("expires_in")
        or payload.get("AUTH_EXPIRES")
        or auth.get("expires_in")
        or 3600
    )
    member_id = (
        payload.get("member_id")
        or payload.get("memberId")
        or payload.get("MEMBER_ID")
        or auth.get("member_id")
    )
    scope = (
        payload.get("scope")
        or payload.get("AUTH_SCOPE")
        or auth.get("scope")
    )

    try:
        expires_in = int(expires_in)
    except Exception:
        expires_in = 3600

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "domain": domain,
        "expires_in": expires_in,
        "member_id": member_id,
        "scope": scope,
    }


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
    body_text = raw_body.decode("utf-8", errors="ignore")
    content_type = request.headers.get("content-type", "")

    if body_text and "application/x-www-form-urlencoded" in content_type:
        parsed_form = flatten_qs_dict(parse_qs(body_text, keep_blank_values=True))
        payload.update(parsed_form)

    elif body_text and "application/json" in content_type:
        try:
            body_json = json.loads(body_text)
            if isinstance(body_json, dict):
                payload.update(body_json)
        except Exception:
            pass

    headers_dict = dict(request.headers)

    save_debug({
        "query_params": dict(request.query_params),
        "payload": payload,
        "headers": headers_dict,
        "raw_body": body_text,
    })

    data = extract_install_payload(payload)

    if not data["access_token"] or not data["refresh_token"] or not data["domain"]:
        return JSONResponse(
            status_code=400,
            content={
                "detail": "Не хватает параметров: access_token, refresh_token, domain",
                "received_keys": list(payload.keys()),
                "received_payload": payload,
            },
        )

    tokens_to_save = {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "domain": data["domain"],
        "expires_at": int(time.time()) + int(data["expires_in"]) - 60,
        "member_id": data["member_id"],
        "scope": data["scope"],
    }
    save_tokens(tokens_to_save)

    return {
        "status": "install_ok",
        "domain": data["domain"],
        "installed": True,
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

    return {
        "status": "task_created",
        "task_id": task_id,
        "bitrix_response": data,
    }
