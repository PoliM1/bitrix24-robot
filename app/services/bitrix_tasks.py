import requests
from sqlalchemy.orm import Session
from app.config import settings
from app.db.models import BitrixInstallation, TaskLog
from app.services.bitrix_auth import refresh_if_needed

class BitrixApiError(Exception):
    pass

def create_task(db: Session, domain: str, title: str, description: str = '', responsible_id: int | None = None, creator_id: int | None = None, deadline: str | None = None):
    installation = db.query(BitrixInstallation).filter(BitrixInstallation.domain == domain, BitrixInstallation.active == True).first()
    if not installation:
        raise BitrixApiError(f'Инсталляция для домена {domain} не найдена')

    installation = refresh_if_needed(db, installation)
    endpoint = installation.client_endpoint or f'https://{domain}/rest/'
    url = endpoint.rstrip('/') + '/tasks.task.add'

    fields = {
        'title': title,
        'description': description,
        'creatorId': creator_id or settings.default_creator_id,
        'responsibleId': responsible_id or settings.default_responsible_id,
    }
    if deadline:
        fields['deadline'] = deadline

    response = requests.post(url, json={
        'auth': installation.access_token,
        'fields': fields,
    }, timeout=30)
    response.raise_for_status()
    data = response.json()

    if 'error' in data:
        raise BitrixApiError(f"{data.get('error')}: {data.get('error_description')}")

    result = data.get('result', {})
    task_id = None
    if isinstance(result, dict):
        task_id = result.get('task', {}).get('id') or result.get('item', {}).get('id')

    log = TaskLog(
        domain=domain,
        title=title,
        responsible_id=fields['responsibleId'],
        creator_id=fields['creatorId'],
        bitrix_task_id=int(task_id) if task_id else None,
        status='created',
    )
    db.add(log)
    db.commit()
    return {'task_id': task_id, 'raw': data}
