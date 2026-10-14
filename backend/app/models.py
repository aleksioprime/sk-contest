"""Реестр моделей для Alembic: импортируйте сюда models.py каждого модуля."""

from app.core.db import Base
from app.modules.audit import models as audit_models
from app.modules.auth import models as auth_models
from app.modules.events import models as events_models
from app.modules.people import models as people_models

__all__ = ['Base', 'audit_models', 'auth_models', 'events_models', 'people_models']
