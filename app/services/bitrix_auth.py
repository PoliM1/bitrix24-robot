from datetime import datetime, timedelta, timezone
import requests
from sqlalchemy.orm import Session
from app.config import settings
from app.db.models import BitrixInstallation

OAUTH_URL = 'https://oauth.bitrix.info/oauth/token/'

def upsert_installation(db: Session, payload: dict) -> BitrixInstallation:
    domain = payload['domain']
    item = db.query(BitrixInstallation).filter(BitrixInstallation.domain == domain).first()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(payload.get('expires_in', 3600)) - 60)
    if not item:
        item = BitrixInstallation(domain=domain)
        db.add(item)
    item.member_id = payload.get('member_id')
    item.access_token = payload['access_token']
    item.refresh_token = payload['refresh_token']
    item.expires_at = expires_at
    item.application_token = payload.get('application_token')
    item.scope = payload.get('scope')
    item.client_endpoint = payload.get('client_endpoint')
    item.server_endpoint = payload.get('server_endpoint')
    item.status = payload.get('status')
    item.active = True
    db.commit()
    db.refresh(item)
    return item

def refresh_if_needed(db: Session, installation: BitrixInstallation) -> BitrixInstallation:
    if installation.expires_at > datetime.now(timezone.utc) + timedelta(minutes=2):
        return installation
    response = requests.get(OAUTH_URL, params={
        'grant_type': 'refresh_token',
        'client_id': settings.bitrix_client_id,
        'client_secret': settings.bitrix_client_secret,
        'refresh_token': installation.refresh_token,
    }, timeout=30)
    response.raise_for_status()
    data = response.json()
    data['domain'] = data.get('domain') or installation.domain
    return upsert_installation(db, data)
