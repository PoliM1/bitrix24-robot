from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.bitrix_auth import upsert_installation

router = APIRouter(tags=['install'])

@router.get('/health')
def health():
    return {'status': 'ok'}

@router.get('/bitrix/install')
async def bitrix_install(request: Request, db: Session = Depends(get_db)):
    params = dict(request.query_params)
    required = ['access_token', 'refresh_token', 'domain']
    missing = [key for key in required if key not in params]
    if missing:
        raise HTTPException(status_code=400, detail=f'Не хватает параметров: {", ".join(missing)}')
    item = upsert_installation(db, params)
    return {
        'status': 'installed',
        'domain': item.domain,
        'expires_at': item.expires_at.isoformat(),
    }
