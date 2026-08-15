from apscheduler.schedulers.background import BackgroundScheduler

from src.utils.config import settings


class Scheduler:
    def __init__(self, func) -> None:
        self.job_func = func

    def start(self):
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            self.job_func,
            "interval",
            seconds=settings.scheduler_interval,
        )
        scheduler.start()
