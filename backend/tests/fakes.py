from app.modules.people.skolstream import SkolstreamProfile

TEACHER_ID = '4f6b2c1e-0000-4000-8000-000000000001'
STUDENT_ID = '4f6b2c1e-0000-4000-8000-000000000002'
CLASS_ID = '7a1d0c55-0000-4000-8000-000000000010'
YEAR_ID = '7a1d0c55-0000-4000-8000-000000000020'
DEPT_ID = '7a1d0c55-0000-4000-8000-000000000030'


class FakeQueue:
    def __init__(self):
        self.jobs: list[tuple[str, tuple, dict]] = []

    async def enqueue(self, function, *args, **kwargs):
        self.jobs.append((function, args, kwargs))


class FakeSkolstream:
    def __init__(self):
        self.profile = SkolstreamProfile(
            id=STUDENT_ID,
            email='student@skolkovo.example.org',
            last_name='Иванова',
            first_name='Анна',
            middle_name='Сергеевна',
            is_student=True,
            class_ids=[CLASS_ID],
        )
        self.directory = directory_payload()
        self.exchanged: list[tuple[str, str, str]] = []

    def authorize_url(self, redirect_uri, state, code_challenge):
        return f'https://skolstream.test/o/authorize/?state={state}&code_challenge={code_challenge}'

    async def exchange_code(self, code, redirect_uri, code_verifier):
        self.exchanged.append((code, redirect_uri, code_verifier))
        return 'skolstream-access-token'

    async def fetch_profile(self, access_token):
        return self.profile

    async def fetch_directory(self, updated_since=None):
        return self.directory


def directory_payload(users=None) -> dict:
    return {
        'academic_years': [
            {'id': YEAR_ID, 'name': '2026/2027', 'is_current': True, 'date_start': '2026-09-01', 'date_end': None}
        ],
        'classes': [{'id': CLASS_ID, 'academic_year_id': YEAR_ID, 'grade': 9, 'letter': 'А', 'name': '9А'}],
        'departments': [{'id': DEPT_ID, 'name': 'Кафедра естественных наук'}],
        'users': users
        if users is not None
        else [
            {
                'id': TEACHER_ID,
                'email': 'teacher@skolkovo.example.org',
                'last_name': 'Петров',
                'first_name': 'Иван',
                'middle_name': 'Олегович',
                'is_employee': True,
                'department_ids': [DEPT_ID],
            },
            {
                'id': STUDENT_ID,
                'email': 'student@skolkovo.example.org',
                'last_name': 'Иванова',
                'first_name': 'Анна',
                'is_student': True,
                'class_ids': [CLASS_ID],
            },
        ],
    }
