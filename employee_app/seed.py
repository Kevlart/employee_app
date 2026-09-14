"""Генерация тестовых данных."""
import random
from datetime import date
from faker import Faker
from models import db, Employee

fake = Faker('ru_RU')


def seed_data(n=500):
    """
    Создаёт n сотрудников с иерархией 5 уровней:
    CEO (1) -> Manager (5) -> Team Lead (25) -> Senior Dev (200) -> Developer (остальные).
    """
    # Чистим таблицу (на случай повторного запуска)
    Employee.query.delete()
    db.session.commit()

    levels = {
        1: ('CEO', 1),
        2: ('Manager', 5),
        3: ('Team Lead', 25),
        4: ('Senior Developer', 200),
        5: ('Developer', max(0, n - 231)),
    }
    level_ids = {i: [] for i in range(1, 6)}

    for level in range(1, 6):
        position, count = levels[level]
        possible_managers = level_ids[level - 1] if level > 1 else []

        for _ in range(count):
            full_name = f'{fake.last_name()} {fake.first_name()} {fake.middle_name()}'
            hire_date = fake.date_between(start_date=date(2000, 1, 1), end_date=date(2023, 12, 31))

            if level == 1:
                salary = random.randint(200000, 300000)
            elif level in (2, 3):
                salary = random.randint(100000, 200000)
            else:
                salary = random.randint(30000, 100000)

            manager_id = random.choice(possible_managers) if possible_managers else None

            emp = Employee(
                full_name=full_name,
                position=position,
                hire_date=hire_date,
                salary=salary,
                manager_id=manager_id,
            )
            db.session.add(emp)
            db.session.flush()   # получаем id до коммита
            level_ids[level].append(emp.id)

        db.session.commit()
        print(f'Уровень {level}: {position} — добавлено {count}')

    print(f'✅ Готово. Всего сотрудников: {Employee.query.count()}')