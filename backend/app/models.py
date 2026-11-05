"""Реестр моделей для Alembic: импортируйте сюда models.py каждого модуля. Люди, вход и журнал — из sk_common."""

from sk_common import models as common_models
from sk_common.db import Base

from app.modules.applications import models as applications_models
from app.modules.evaluation import models as evaluation_models
from app.modules.events import models as events_models
from app.modules.files import models as files_models
from app.modules.stages import models as stages_models

__all__ = [
    'Base',
    'applications_models',
    'common_models',
    'evaluation_models',
    'events_models',
    'files_models',
    'stages_models',
]
