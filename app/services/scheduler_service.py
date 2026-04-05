from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from app.config import settings
from app.db.database import SessionLocal
from app.db.models import BitrixInstallation, TaskLog
from app.services.bitrix_tasks import create_task

scheduler = BackgroundScheduler(timezone='Asia/Yakutsk')


def scheduled_job():
    db: Session = SessionLocal()
    try:
        installations = db.query(BitrixInstallation).filter(BitrixInstallation.active == True).all()
        for inst in installations:
            title = 'Автоматическая задача от робота'
            description = 'Задача создана по расписанию серверным приложением без webhook.'
            try:
                create_task(db, inst.domain, title, description)
            except Exception as e:
                db.add(TaskLog(
                    domain=inst.domain,
                    title=title,
                    responsible_id=settings.default_responsible_id,
                    creator_id=settings.default_creator_id,
                    status='error',
                    error_text=str(e),
                ))
                db.commit()
    finally:
        db.close()


def start_scheduler():
    if not settings.scheduler_enabled:
        return
    minute, hour, day, month, day_of_week = settings.schedule_cron.split()
    scheduler.add_job(scheduled_job, 'cron', minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week, id='bitrix_task_job', replace_existing=True)
    scheduler.start()
