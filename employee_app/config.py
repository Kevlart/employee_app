"""Настройки приложения."""

# Секретный ключ нужен для flash-сообщений
SECRET_KEY = 'простой-секретный-ключ'

# По умолчанию — SQLite (файл создастся сам).
# Для PostgreSQL раскомментируй строку ниже и поменяй данные:
# SQLALCHEMY_DATABASE_URI = 'postgresql://employees_user:employees_pass@localhost:5432/employees'
SQLALCHEMY_DATABASE_URI = 'sqlite:///employees.db'

# Белый список полей для сортировки (защита от SQL-инъекций)
ALLOWED_SORT_FIELDS = {'id', 'full_name', 'position', 'hire_date', 'salary'} 