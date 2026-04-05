from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.config import settings
from app.db.database import get_db
from app.services.bitrix_tasks import BitrixApiError, create_task

router = APIRouter(prefix='/tasks', tags=['tasks'])

class TaskCreateSchema(BaseModel):
    domain: str | None = None
    title: str
    description: str = ''
    responsible_id: int | None = None
    creator_id: int | None = None
    deadline: str | None = None

@router.post('/create')
def create_task_endpoint(payload: TaskCreateSchema, db: Session = Depends(get_db)):
    domain = payload.domain or settings.default_bitrix_domain
    if not domain:
        raise HTTPException(status_code=400, detail='Не указан domain')
    try:
        return create_task(
            db=db,
            domain=domain,
            title=payload.title,
            description=payload.description,
            responsible_id=payload.responsible_id,
            creator_id=payload.creator_id,
            deadline=payload.deadline,
        )
    except BitrixApiError as e:
        raise HTTPException(status_code=400, detail=str(e))
