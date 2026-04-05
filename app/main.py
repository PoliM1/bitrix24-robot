from fastapi import FastAPI
from app.db.database import Base, engine
from app.routers.install import router as install_router
from app.routers.tasks import router as tasks_router
from app.services.scheduler_service import start_scheduler

Base.metadata.create_all(bind=engine)
app = FastAPI(title='Bitrix24 Robot')
app.include_router(install_router)
app.include_router(tasks_router)

@app.on_event('startup')
def on_startup():
    start_scheduler()
