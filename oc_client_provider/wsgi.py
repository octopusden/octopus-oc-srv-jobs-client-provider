import logging
from .app import create_app
from .config import Config
import os
from oc_orm_initializator.orm_initializator import OrmInitializator

_settings = {"installed_apps": [
        "oc_delivery_apps.checksums",
        "oc_delivery_apps.dlmanager"]}

for _s in ["url", "user", "password"]:
    _env = "_".join(["psql", _s]).upper()
    _v = os.getenv(_env)

    if not _v:
        raise ValueError("Environment '%s' is not set" % _env)

    _settings[_s] = _v

# time_zone is not required and may be overwritten
_settings["TIME_ZONE"] = os.getenv("DJANGO_TIME_ZONE") or os.getenv("DJANGO_TIMEZONE") or "Etc/UTC"

OrmInitializator(**_settings)
app = create_app(Config)

# additional tricks for logging
if __name__ != "__main__":
    gunicorn_logger = logging.getLogger("gunicorn.error")
    logging.basicConfig(format='[%(asctime)s] [%(levelname)s] %(message)s', level=gunicorn_logger.level)
