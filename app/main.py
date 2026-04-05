from fastapi import FastAPI
from app.db.database import Base, engine
from app.routers.install import router as install_router
from app.routers.tasks import router as tasks_router
from app.services.scheduler_service import start_scheduler

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/bitrix/install")
async def install(auth: str, client_id: str, domain: str, 
                  access_token: str, refresh_token: str):
    # сохранить токены в БД
    return {"status": "install_ok"}

@app.post("/bitrix/task/create")
async def create_task(title: str, responsible_id: int):
    # создать задачу через Bitrix24 API
    return {"status": "task_created", "task_id": 123}

Base.metadata.create_all(bind=engine)
app = FastAPI(title='Bitrix24 Robot')
app.include_router(install_router)
app.include_router(tasks_router)

@app.on_event('startup')
def on_startup():
    start_scheduler()
