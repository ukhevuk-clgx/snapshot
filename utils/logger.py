from datetime import datetime
class Logger:
    @staticmethod
    def _ts(): return datetime.now().strftime("%H:%M:%S")
    @classmethod
    def info(cls,m): print(f"[{cls._ts()}] [INFO] {m}",flush=True)
    @classmethod
    def warning(cls,m): print(f"[{cls._ts()}] [WARN] {m}",flush=True)
    @classmethod
    def error(cls,m): print(f"[{cls._ts()}] [ERROR] {m}",flush=True)
