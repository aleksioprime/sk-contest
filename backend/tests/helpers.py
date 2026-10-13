from app.core.config import settings
from app.modules.auth.service import open_session
from app.modules.people.models import Person, User


async def login_as(db, client, email='admin@skolkovo.example.org', is_superuser=False, last_name='Админов') -> User:
    """Создать пользователя и положить cookie сессии в клиент."""
    person = Person(email=email, last_name=last_name, first_name='Тест')
    db.add(person)
    await db.flush()
    user = User(email=email, person=person, is_superuser=is_superuser)
    db.add(user)
    await db.flush()
    access, _ = await open_session(db, user, 'magic_link', 'pytest', '127.0.0.1')
    await db.commit()
    client.cookies.set(settings.auth.access_cookie, access)
    return user
