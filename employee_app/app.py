"""Flask-приложение: управление сотрудниками."""
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, abort
)
from config import SECRET_KEY, SQLALCHEMY_DATABASE_URI, ALLOWED_SORT_FIELDS
from models import db, Employee
from seed import seed_data

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)


# ---------- Создание базы при первом запуске ----------
@app.before_request
def create_tables():
    """Создаёт таблицы, если их нет. Выполняется один раз."""
    if not getattr(app, '_db_ready', False):
        with app.app_context():
            db.create_all()
        app._db_ready = True


# ---------- Главная страница со списком ----------
@app.route('/')
def index():
    sort_by = request.args.get('sort_by', 'id')
    order = request.args.get('order', 'asc')
    search = request.args.get('search', '').strip()
    position = request.args.get('position', '').strip()

    # Защита от подстановки произвольных полей
    if sort_by not in ALLOWED_SORT_FIELDS:
        sort_by = 'id'
    if order not in ('asc', 'desc'):
        order = 'asc'

    column = getattr(Employee, sort_by)
    query = Employee.query

    if search:
        query = query.filter(Employee.full_name.ilike(f'%{search}%'))
    if position:
        query = query.filter(Employee.position == position)

    query = query.order_by(column.desc() if order == 'desc' else column.asc())
    employees = query.all()

    # Уникальные должности для выпадающего фильтра
    positions = [p[0] for p in db.session.query(Employee.position).distinct().all()]

    return render_template(
        'index.html',
        employees=employees,
        sort_by=sort_by,
        order=order,
        search=search,
        position=position,
        positions=positions,
    )


# ---------- Дерево иерархии ----------
@app.route('/tree')
def tree():
    position_filter = request.args.get('position', '').strip()
    limit = request.args.get('limit', type=int)

    # Строим полное дерево: начинаем с корней (manager_id is None)
    roots = Employee.query.filter_by(manager_id=None).all()

    lines = []

    def walk(emp, level=0):
        lines.append((level, emp))
        for sub in sorted(emp.subordinates, key=lambda e: e.full_name):
            walk(sub, level + 1)

    for root in roots:
        walk(root)

    # Фильтр по должности: показываем только ветки, где она встречается
    if position_filter:
        target_ids = {
            e.id for e in Employee.query.filter_by(position=position_filter).all()
        }
        if not target_ids:
            flash(f'Должность "{position_filter}" не найдена.', 'warning')
            lines = []
        else:
            # Оставляем строки, где в ветке до узла есть искомая должность
            # (упрощённо: оставим узлы, у которых хотя бы один подчинённый подходит,
            #  либо сам узел подходит)
            filtered = []
            for lvl, emp in lines:
                descendants = _all_descendants(emp)
                if emp.id in target_ids or (descendants & target_ids):
                    filtered.append((lvl, emp))
            lines = filtered

    if limit:
        lines = lines[:limit]

    return render_template('tree.html', lines=lines, position_filter=position_filter)


def _all_descendants(emp):
    """Возвращает set id всех подчинённых (рекурсивно)."""
    result = set()
    for sub in emp.subordinates:
        result.add(sub.id)
        result |= _all_descendants(sub)
    return result


# ---------- Добавление сотрудника ----------
@app.route('/employee/add', methods=['GET', 'POST'])
def add_employee():
    if request.method == 'POST':
        try:
            full_name = request.form['full_name'].strip()
            position = request.form['position'].strip()
            hire_date = request.form['hire_date']
            salary = int(request.form['salary'])
            manager_id = request.form.get('manager_id') or None

            if not full_name or not position or not hire_date:
                flash('Заполните все обязательные поля.', 'danger')
                return redirect(url_for('add_employee'))

            if salary < 0:
                flash('Зарплата не может быть отрицательной.', 'danger')
                return redirect(url_for('add_employee'))

            if manager_id:
                manager_id = int(manager_id)
                if not Employee.query.get(manager_id):
                    flash('Начальник с таким ID не найден.', 'danger')
                    return redirect(url_for('add_employee'))

            from datetime import datetime
            emp = Employee(
                full_name=full_name,
                position=position,
                hire_date=datetime.strptime(hire_date, '%Y-%m-%d').date(),
                salary=salary,
                manager_id=manager_id,
            )
            db.session.add(emp)
            db.session.commit()
            flash(f'Сотрудник {full_name} добавлен (ID={emp.id}).', 'success')
            return redirect(url_for('index'))

        except ValueError as e:
            db.session.rollback()
            flash(f'Ошибка в данных: {e}', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Не удалось добавить: {e}', 'danger')

    return render_template('employee_form.html', employee=None, title='Добавить сотрудника')


# ---------- Редактирование сотрудника ----------
@app.route('/employee/<int:emp_id>/edit', methods=['GET', 'POST'])
def edit_employee(emp_id):
    emp = Employee.query.get_or_404(emp_id)

    if request.method == 'POST':
        try:
            emp.full_name = request.form['full_name'].strip()
            emp.position = request.form['position'].strip()
            from datetime import datetime
            emp.hire_date = datetime.strptime(request.form['hire_date'], '%Y-%m-%d').date()
            emp.salary = int(request.form['salary'])

            manager_id = request.form.get('manager_id') or None
            if manager_id:
                manager_id = int(manager_id)
                if manager_id == emp_id:
                    flash('Нельзя назначить сотрудника начальником самому себе.', 'danger')
                    return redirect(url_for('edit_employee', emp_id=emp_id))
                # Проверка на цикл
                forbidden = {emp_id} | _all_descendants(emp)
                if manager_id in forbidden:
                    flash('Нельзя — получится цикл в иерархии.', 'danger')
                    return redirect(url_for('edit_employee', emp_id=emp_id))
            emp.manager_id = manager_id

            db.session.commit()
            flash('Данные обновлены.', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении: {e}', 'danger')

    return render_template('employee_form.html', employee=emp, title='Редактировать сотрудника')


# ---------- Удаление ----------
@app.route('/employee/<int:emp_id>/delete', methods=['POST'])
def delete_employee(emp_id):
    emp = Employee.query.get_or_404(emp_id)
    try:
        # Открепляем подчинённых
        for sub in emp.subordinates:
            sub.manager_id = None
        db.session.delete(emp)
        db.session.commit()
        flash(f'Сотрудник {emp.full_name} удалён.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка удаления: {e}', 'danger')
    return redirect(url_for('index'))


# ---------- Быстрая смена начальника ----------
@app.route('/employee/<int:emp_id>/edit_manager', methods=['GET', 'POST'])
def edit_manager(emp_id):
    emp = Employee.query.get_or_404(emp_id)

    # Запрещаем выбирать самого себя и всех своих подчинённых
    forbidden = {emp_id} | _all_descendants(emp)
    candidates = Employee.query.filter(~Employee.id.in_(forbidden)).all()

    if request.method == 'POST':
        manager_id = request.form.get('manager_id') or None
        try:
            emp.manager_id = int(manager_id) if manager_id else None
            db.session.commit()
            flash('Начальник обновлён.', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {e}', 'danger')

    return render_template('edit_manager.html', employee=emp, candidates=candidates)


# ---------- Сиды через веб ----------
@app.route('/seed')
def seed_route():
    try:
        n = request.args.get('n', 50000, type=int)
        seed_data(n)
        flash(f'Создано {n} тестовых сотрудников.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка генерации: {e}', 'danger')
    return redirect(url_for('index'))


# ---------- Обработчики ошибок ----------
@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', code=404, message='Страница не найдена'), 404


@app.errorhandler(500)
def server_error(e):
    db.session.rollback()
    return render_template('error.html', code=500, message='Ошибка на сервере'), 500


if __name__ == '__main__':
    app.run(debug=True)
