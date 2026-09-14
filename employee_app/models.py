"""Модели базы данных."""
from datetime import date
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Employee(db.Model):
    __tablename__ = 'employees'

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False, index=True)
    position = db.Column(db.String(150), nullable=False, index=True)
    hire_date = db.Column(db.Date, nullable=False)
    salary = db.Column(db.Integer, nullable=False)
    manager_id = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='SET NULL'))

    # Связь "начальник — подчинённые" (ссылка на самого себя)
    manager = db.relationship(
        'Employee',
        remote_side=[id],
        backref=db.backref('subordinates', cascade='all, delete-orphan')
    )

    def to_dict(self):
        """Для отладки/API."""
        return {
            'id': self.id,
            'full_name': self.full_name,
            'position': self.position,
            'hire_date': self.hire_date.isoformat(),
            'salary': self.salary,
            'manager_id': self.manager_id,
        }

    def __repr__(self):
        return f'<Employee {self.id} {self.full_name}>'