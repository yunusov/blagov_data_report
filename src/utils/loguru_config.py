from loguru import logger


class AppLogger:
    _instance = None
    _current_dir = None

    def __new__(cls, current_dir=None):
        cls._current_dir = current_dir
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._setup_logging()
        return cls._instance

    def _setup_logging(self):
        """
        Настраивает логгер для всего приложения.
        """
        # Удаляем стандартный обработчик, чтобы избежать дублирования
        logger.remove()

        # В файл пишем все, начиная с DEBUG, в формате JSON для машинного анализа
        log_file = "logs/app.log"
        log_file = self._current_dir / log_file if self._current_dir else log_file

        logger.add(
            log_file,
            level="DEBUG",
            rotation="10 MB",
            retention="1 month",
            compression="zip",
            serialize=False,  # Структурированное логирование в JSON
        )
        # logger.info("Режим продакшена: логирование настроено для вывода в файл.")

    def get_logger(self):
        return logger
