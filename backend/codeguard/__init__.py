# CODEGUARD Django Project Init
import pymysql

pymysql.install_as_MySQLdb()

# Celery application import
from .celery import app as celery_app

__all__ = ('celery_app',)
