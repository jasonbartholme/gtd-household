import calendar
import os
from datetime import datetime, date, timedelta
from flask import Flask, request, redirect, url_for, session, flash, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from zoneinfo import ZoneInfo

# ==========================================
# 1. APP CONFIGURATION
# ==========================================
# template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))
app = Flask(__name__)
app.config['SECRET_KEY'] = 'lan-local-secret-key-modifqy-in-prod'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gtd.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

def get_local_now():
    """Returns current time in Central Time (US/Chicago) as a naive datetime for SQLite."""
    return datetime.now(ZoneInfo("America/Chicago")).replace(tzinfo=None)

# ==========================================
# 2. DATABASE MODELS
# ==========================================
class Household(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=get_local_now)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(20), default='member') # admin, member
    weekday_capacity_points = db.Column(db.Integer, default=20)
    weekend_capacity_points = db.Column(db.Integer, default=30)

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default='active') # active, completed
    created_at = db.Column(db.DateTime, default=get_local_now)
    completed_at = db.Column(db.DateTime, nullable=True)

    actions = db.relationship('ActionItem', backref='project', lazy=True)

class InboxItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False)
    captured_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    title = db.Column(db.String(200), nullable=False)
    context = db.Column(db.String(100), nullable=True)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=get_local_now)
    processed_at = db.Column(db.DateTime, nullable=True)
    converted_action_id = db.Column(db.Integer, db.ForeignKey('action_item.id'), nullable=True)

action_asset = db.Table('action_asset',
    db.Column('action_id', db.Integer, db.ForeignKey('action_item.id'), primary_key=True),
    db.Column('asset_id', db.Integer, db.ForeignKey('asset.id'), primary_key=True)
)

action_supply = db.Table('action_supply',
    db.Column('action_id', db.Integer, db.ForeignKey('action_item.id'), primary_key=True),
    db.Column('supply_id', db.Integer, db.ForeignKey('supply.id'), primary_key=True)
)

asset_supply = db.Table('asset_supply',
    db.Column('asset_id', db.Integer, db.ForeignKey('asset.id'), primary_key=True),
    db.Column('supply_id', db.Integer, db.ForeignKey('supply.id'), primary_key=True)
)

class ActionItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    context = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    item_type = db.Column(db.String(20), default='task') # task, chore, errand
    status = db.Column(db.String(20), default='ready') # ready, in_progress, blocked, done, waiting, someday
    complexity_fib = db.Column(db.Integer, default=1)
    base_points = db.Column(db.Integer, default=10)
    owner_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=get_local_now)
    completed_at = db.Column(db.DateTime, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)

    is_recurring = db.Column(db.Boolean, default=False)
    recur_interval = db.Column(db.Integer, default=1)
    recur_unit = db.Column(db.String(20)) # days, weeks, months

    lat = db.Column(db.Float, nullable=True)
    lng = db.Column(db.Float, nullable=True)

    assets = db.relationship('Asset', secondary=action_asset, backref=db.backref('actions', lazy=True))
    supplies = db.relationship('Supply', secondary=action_supply, backref=db.backref('actions', lazy=True))

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action_type = db.Column(db.String(50))
    description = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=get_local_now)

class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))
    context = db.Column(db.String(100))
    status = db.Column(db.String(50), default='available')
    notes = db.Column(db.Text)
    checked_out_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    checked_out_at = db.Column(db.DateTime, nullable=True)
    qr_code_ref = db.Column(db.String(100), unique=True, nullable=True)
    purchase_url = db.Column(db.String(500))

    power_source = db.Column(db.String(50))
    battery_type = db.Column(db.String(50))
    battery_lifespan_days = db.Column(db.Integer, nullable=True)

    maintenance_schedules = db.relationship('MaintenanceSchedule', backref='asset', lazy=True)
    expenses = db.relationship('Expense', backref='asset_rel', lazy=True)
    supplies = db.relationship('Supply', secondary=asset_supply, backref=db.backref('assets', lazy=True))

class MaintenanceSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    frequency_days = db.Column(db.Integer, nullable=False)
    last_completed = db.Column(db.DateTime, nullable=True)
    next_due = db.Column(db.DateTime, nullable=True)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    date = db.Column(db.DateTime, default=get_local_now)

    is_maintenance = db.Column(db.Boolean, default=False)
    maintenance_schedule_id = db.Column(db.Integer, db.ForeignKey('maintenance_schedule.id'), nullable=True)

class Supply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    reorder_threshold = db.Column(db.Integer, default=0)
    auto_add_to_shopping = db.Column(db.Boolean, default=True)
    context = db.Column(db.String(100))
    purchase_url = db.Column(db.String(500))
    store_name = db.Column(db.String(100))

class HouseholdList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    tags = db.Column(db.String(200), nullable=True)
    location_context = db.Column(db.String(100), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=get_local_now)

    items = db.relationship('ListItem', backref='list', lazy=True, cascade="all, delete-orphan", order_by="ListItem.sort_order")
    owner = db.relationship('User', backref='lists_owned', lazy=True)

class ListItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False)
    list_id = db.Column(db.Integer, db.ForeignKey('household_list.id'), nullable=True)
    content = db.Column(db.String(255), nullable=False)
    is_checked = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=get_local_now)

def log_activity(user_id, action_type, description):
    if user_id:
        db.session.add(ActivityLog(user_id=user_id, action_type=action_type, description=description))
        db.session.commit()

# ==========================================
# 4. UTILS & MIDDLEWARE
# ==========================================
@app.context_processor
def inject_global_data():
    current_user_id = session.get('user_id')
    current_user = db.session.get(User, current_user_id) if current_user_id else None
    all_users = User.query.all()

    hid = session.get('household_id')
    all_projects = Project.query.filter_by(household_id=hid, status='active').all() if hid else []

    # Global unprocessed inbox count
    unproc_inbox = InboxItem.query.filter_by(household_id=hid, processed_at=None).count() if hid else 0

    # Dynamic Page Titles
    endpoints = {
        'dashboard': 'Dashboard',
        'leaderboard': 'Leaderboard',
        'kanban': 'Board',
        'inbox': 'Inbox',
        'review': 'Review',
        'manage_projects': 'Projects',
        'manage_lists': 'Lists',
        'someday_view': 'Someday/Maybe',
        'calendar_view': 'Calendar',
        'assets': 'Assets',
        'supplies': 'Supplies',
        'project_detail': 'Project Details',
        'view_list': 'List Details',
        'asset_detail': 'Asset Details',
        'manage_users': 'Users'
    }
    page_title = endpoints.get(request.endpoint, '')

    return dict(
        current_user=current_user,
        all_users=all_users,
        all_projects=all_projects,
        today=get_local_now().date(),
        unproc_inbox=unproc_inbox,
        page_title=page_title
    )
first_run = True

def setup_db():
    # Ensure the database tables exist and seed minimal data once per process
    db.create_all()
    if not Household.query.first():
        h = Household(name="Local Household")
        db.session.add(h)
        db.session.commit()
        u1 = User(name="Admin", role="admin", household_id=h.id)
        u2 = User(name="Member", role="member", household_id=h.id)
        db.session.add_all([u1, u2])
        db.session.commit()

        p1 = Project(household_id=h.id, name="Garage Organization", description="Clean out the garage before winter so we can park both cars inside.")
        db.session.add(p1)

        drone = Asset(household_id=h.id, name="Drone Kit", category="electronics", context="Office", power_source="Battery", battery_type="Proprietary Lipo", battery_lifespan_days=365)
        vw = Asset(household_id=h.id, name="VW Wagen", category="vehicle", context="Garage", power_source="Gas")
        cleaner = Supply(household_id=h.id, name="Toilet Cleaner", quantity=1, reorder_threshold=0, context="Kitchen pantry")

        oil = Supply(household_id=h.id, name="Synthetic Oil 5W-30", quantity=2, reorder_threshold=1, context="Garage")
        oil_filter = Supply(household_id=h.id, name="Oil Filter", quantity=1, reorder_threshold=0, context="Garage")

        db.session.add_all([drone, vw, cleaner, oil, oil_filter])
        vw.supplies.extend([oil, oil_filter])
        db.session.commit()

        vw_oil = MaintenanceSchedule(asset_id=vw.id, name="Synthetic Oil Change", frequency_days=180, next_due=get_local_now() + timedelta(days=30))
        drone_bat = MaintenanceSchedule(asset_id=drone.id, name="Replace Battery", frequency_days=365, next_due=get_local_now() - timedelta(days=5))
        db.session.add_all([vw_oil, drone_bat])
        db.session.commit()

    app._setup_done = True


@app.before_request
def ensure_session_user():
    # Keep session population separate from DB setup so requests don't fail if DB was empty
    if 'user_id' not in session and request.endpoint not in ['static', None]:
        first_user = User.query.first()
        if first_user:
            session['user_id'] = first_user.id
            session['household_id'] = first_user.household_id

def calculate_next_due_date(current_date, interval, unit):
    if not current_date:
        current_date = get_local_now()
    if unit == 'days':
        return current_date + timedelta(days=interval)
    elif unit == 'weeks':
        return current_date + timedelta(weeks=interval)
    elif unit == 'months':
        new_month = current_date.month + interval
        year = current_date.year + (new_month - 1) // 12
        month = (new_month - 1) % 12 + 1
        return current_date.replace(year=year, month=month)
    return current_date

# ==========================================
# 5. ROUTES
# ==========================================

# ========== Healthcheck helper & endpoint ==========
def get_health_status():
    """Return a simple health payload: DB connection and basic counts."""
    try:
        # quick raw query to ensure DB engine responds
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))

        users_count = User.query.count()
        actions_count = ActionItem.query.count()
        unproc_inbox = InboxItem.query.filter_by(processed_at=None).count()
        last_activity = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).first()
        last_activity_ts = last_activity.timestamp.isoformat() if last_activity else None

        return {
            'status': 'ok',
            'db_connected': True,
            'counts': {
                'users': users_count,
                'actions': actions_count,
                'unprocessed_inbox': unproc_inbox
            },
            'last_activity': last_activity_ts
        }
    except Exception as e:
        return {
            'status': 'error',
            'db_connected': False,
            'error': str(e)
        }


@app.route('/health')
def health():
    return jsonify(get_health_status())


@app.route('/')
def kanban():
    hid = session.get('household_id')
    items = ActionItem.query.filter(ActionItem.household_id==hid, ActionItem.status != 'someday').order_by(ActionItem.created_at.desc()).all()
    return render_template("kanban.html", items=items)

@app.route('/projects')
def manage_projects():
    hid = session.get('household_id')
    projects = Project.query.filter_by(household_id=hid).order_by(Project.status, Project.created_at.desc()).all()
    return render_template('projects.html', projects=projects)

@app.route('/projects/add', methods=['POST'])
def add_project():
    p = Project(
        household_id=session.get('household_id'),
        name=request.form.get('name'),
        description=request.form.get('description')
    )
    db.session.add(p)
    db.session.commit()
    flash(f"Created Project: {p.name}", "success")
    return redirect(url_for('manage_projects'))

@app.route('/projects/<int:id>')
def project_detail(id):
    project = db.session.get(Project, id)
    return render_template('project_detail.html', project=project)

@app.route('/projects/<int:id>/toggle', methods=['POST'])
def toggle_project_status(id):
    project = db.session.get(Project, id)
    if project.status == 'active':
        project.status = 'completed'
        project.completed_at = get_local_now()
        flash("Project marked as completed!", "success")
    else:
        project.status = 'active'
        project.completed_at = None
        flash("Project reopened.", "info")
    db.session.commit()
    return redirect(url_for('project_detail', id=project.id))

@app.route('/someday')
def someday_view():
    hid = session.get('household_id')
    items = ActionItem.query.filter_by(household_id=hid, status='someday').order_by(ActionItem.created_at.desc()).all()
    return render_template('someday.html', items=items)

@app.route('/someday/<int:id>/activate', methods=['POST'])
def activate_someday(id):
    item = db.session.get(ActionItem, id)
    item.status = 'ready'
    db.session.commit()
    flash(f"Activated '{item.title}'! It is now on your active Kanban board.", "success")
    return redirect(url_for('someday_view'))

@app.route('/inbox')
def inbox():
    hid = session.get('household_id')
    items = InboxItem.query.filter_by(household_id=hid, processed_at=None).order_by(InboxItem.created_at.desc()).all()
    return render_template('inbox.html', inbox_items=items)

@app.route('/inbox/add', methods=['POST'])
def add_inbox():
    db.session.add(InboxItem(household_id=session['household_id'], captured_by_user_id=session['user_id'],
                             title=request.form.get('title'), context=request.form.get('context'), note=request.form.get('note')))
    db.session.commit()
    flash("Captured!", "success")
    return redirect(url_for('inbox'))

@app.route('/inbox/add_bulk', methods=['POST'])
def add_inbox_bulk():
    bulk_text = request.form.get('bulk_items', '')
    context = request.form.get('context', '')
    items = [line.strip() for line in bulk_text.split('\n') if line.strip()]
    for item_title in items:
        db.session.add(InboxItem(
            household_id=session['household_id'],
            captured_by_user_id=session['user_id'],
            title=item_title,
            context=context
        ))
    db.session.commit()
    flash(f"Captured {len(items)} items to Inbox!", "success")
    return redirect(url_for('inbox'))

@app.route('/inbox/process/<int:item_id>', methods=['POST'])
def process_inbox(item_id):
    inbox_item = db.session.get(InboxItem, item_id)
    due_date_str = request.form.get('due_date')
    due_date = datetime.strptime(due_date_str, '%Y-%m-%d') if due_date_str else None

    interval = request.form.get('recur_interval')
    is_recurring = bool(interval and int(interval) > 0)

    project_id = request.form.get('project_id')
    status = request.form.get('status', 'ready')

    action = ActionItem(
        household_id=session['household_id'],
        title=request.form.get('title'),
        description=request.form.get('description'),
        item_type=request.form.get('item_type'),
        complexity_fib=int(request.form.get('complexity_fib')),
        context=request.form.get('context'),
        project_id=int(project_id) if project_id else None,
        status=status,
        owner_user_id=session['user_id'],
        due_date=due_date,
        is_recurring=is_recurring,
        recur_interval=int(interval) if is_recurring else 1,
        recur_unit=request.form.get('recur_unit') if is_recurring else 'days'
    )
    db.session.add(action)
    inbox_item.processed_at = get_local_now()
    db.session.commit()

    if status == 'someday':
        flash("Action sent to Someday incubator.", "info")
    else:
        flash("Action added to board.", "success")

    return redirect(url_for('kanban'))

@app.route('/action/<int:id>/edit', methods=['GET', 'POST'])
def edit_action(id):
    action = db.session.get(ActionItem, id)
    if request.method == 'POST':
        action.title = request.form.get('title')
        action.item_type = request.form.get('item_type')
        action.complexity_fib = int(request.form.get('complexity_fib'))
        action.context = request.form.get('context')
        action.description = request.form.get('description')
        action.status = request.form.get('status')
        project_id = request.form.get('project_id')
        action.project_id = int(project_id) if project_id else None
        action.is_recurring = 'is_recurring' in request.form
        action.recur_interval = int(request.form.get('recur_interval') or 1)
        action.recur_unit = request.form.get('recur_unit')
        due_date_str = request.form.get('due_date')
        action.due_date = datetime.strptime(due_date_str, '%Y-%m-%d') if due_date_str else None
        asset_ids = request.form.getlist('assets')
        action.assets = Asset.query.filter(Asset.id.in_(asset_ids)).all()
        supply_ids = request.form.getlist('supplies')
        action.supplies = Supply.query.filter(Supply.id.in_(supply_ids)).all()

        db.session.commit()
        log_activity(session.get('user_id'), 'edit_action', f"Updated: {action.title}")
        flash("Action updated.", "success")
        return redirect(url_for('kanban'))

    hid = session.get('household_id')
    all_assets = Asset.query.filter_by(household_id=hid).all()
    all_supplies = Supply.query.filter_by(household_id=hid).all()
    return render_template('action_edit.html', action=action, all_assets=all_assets, all_supplies=all_supplies)

@app.route('/api/update_status/<int:item_id>', methods=['POST'])
def update_status(item_id):
    action = db.session.get(ActionItem, item_id)
    new_status = request.get_json().get('status')
    respawned = False

    if new_status in ['ready', 'in_progress', 'blocked', 'done']:
        action.status = new_status
        if new_status == 'done':
            action.completed_at = get_local_now()
            action.owner_user_id = session.get('user_id')
            log_activity(session.get('user_id'), 'completed_task', f"Finished: {action.title}")

            if action.is_recurring:
                new_due = calculate_next_due_date(action.due_date or get_local_now(), action.recur_interval, action.recur_unit)
                new_action = ActionItem(
                    household_id=action.household_id,
                    title=action.title,
                    description=action.description,
                    item_type=action.item_type,
                    complexity_fib=action.complexity_fib,
                    context=action.context,
                    project_id=action.project_id,
                    is_recurring=True,
                    recur_interval=action.recur_interval,
                    recur_unit=action.recur_unit,
                    due_date=new_due,
                    status='ready'
                )
                new_action.assets = action.assets
                new_action.supplies = action.supplies

                db.session.add(new_action)
                respawned = True
                log_activity(session.get('user_id'), 'recurrence_respawn', f"Scheduled next: {action.title} for {new_due.strftime('%Y-%m-%d')}")

        db.session.commit()
        return jsonify(success=True, respawned=respawned)
    return jsonify(success=False), 400

@app.route('/review')
def review():
    hid = session.get('household_id')
    inbox_count = InboxItem.query.filter_by(household_id=hid, processed_at=None).count()
    someday_count = ActionItem.query.filter_by(household_id=hid, status='someday').count()
    waiting = ActionItem.query.filter_by(household_id=hid, status='waiting').all()

    recurring = ActionItem.query.filter_by(household_id=hid, is_recurring=True).all()
    active_recurring = [item for item in recurring if item.status != 'done']

    return render_template('review.html', inbox_count=inbox_count, someday_count=someday_count, waiting_items=waiting, recurring_items=active_recurring)

@app.route('/dashboard')
def dashboard():
    today = get_local_now().date()
    activity = ActivityLog.query.filter(ActivityLog.timestamp >= today).order_by(ActivityLog.timestamp.desc()).all()
    completions = ActionItem.query.filter(ActionItem.completed_at >= today).count()

    hid = session.get('household_id')
    active_lists_count = HouseholdList.query.filter_by(household_id=hid, is_deleted=False).count() if hid else 0

    purge_cutoff = get_local_now() - timedelta(days=30)
    purgeable_lists_count = HouseholdList.query.filter(HouseholdList.household_id == hid, HouseholdList.is_deleted == True, HouseholdList.deleted_at <= purge_cutoff).count() if hid else 0
    purgeable_items_count = ListItem.query.filter(ListItem.household_id == hid, ListItem.is_deleted == True, ListItem.deleted_at <= purge_cutoff).count() if hid else 0

    return render_template('dashboard.html', activity=activity, today_completions=completions,
                           active_lists_count=active_lists_count,
                           purgeable_lists_count=purgeable_lists_count,
                           purgeable_items_count=purgeable_items_count)

@app.route('/leaderboard')
def leaderboard():
    hid = session.get('household_id')
    completed_items = ActionItem.query.filter_by(household_id=hid, status='done').all()
    users = {u.id: u.name for u in User.query.filter_by(household_id=hid).all()}

    daily_scores = {}
    for item in completed_items:
        if not item.owner_user_id or not item.completed_at:
            continue
        d_str = item.completed_at.date().isoformat()
        key = (item.owner_user_id, d_str)
        daily_scores[key] = daily_scores.get(key, 0) + item.complexity_fib

    today_str = get_local_now().date().isoformat()
    todays_points = [{'name': users.get(uid, 'Unknown'), 'points': pts}
                     for (uid, d_str), pts in daily_scores.items() if d_str == today_str]
    todays_points.sort(key=lambda x: x['points'], reverse=True)

    all_scores = [{'name': users.get(uid, 'Unknown'), 'date': d_str, 'points': pts}
                  for (uid, d_str), pts in daily_scores.items()]

    top_scores = sorted(all_scores, key=lambda x: x['points'], reverse=True)[:10]
    recent_scores = sorted(all_scores, key=lambda x: x['date'], reverse=True)[:10]

    return render_template('leaderboard.html', todays_points=todays_points, top_scores=top_scores, recent_scores=recent_scores)

@app.route('/calendar')
@app.route('/calendar/<int:year>/<int:month>')
def calendar_view(year=None, month=None):
    today = get_local_now().date()
    if year is None or month is None:
        year = today.year
        month = today.month

    first_of_month = date(year, month, 1)
    prev_month_date = first_of_month - timedelta(days=1)
    next_month_date = first_of_month + timedelta(days=32)
    next_month_date = date(next_month_date.year, next_month_date.month, 1)

    hid = session.get('household_id')
    actions = ActionItem.query.filter(
        ActionItem.household_id == hid,
        ActionItem.due_date >= first_of_month,
        ActionItem.due_date < next_month_date
    ).all()

    cal = calendar.Calendar(firstweekday=6)
    weeks_raw = cal.monthdays2calendar(year, month)
    calendar_weeks = []

    for week_raw in weeks_raw:
        week = []
        for day_num, weekday in week_raw:
            in_month = day_num != 0
            day_events = []
            if in_month:
                current_dt = date(year, month, day_num)
                day_events = [a for a in actions if a.due_date and a.due_date.date() == current_dt]
            week.append({
                'day_num': day_num if day_num > 0 else "",
                'in_month': in_month,
                'is_today': in_month and today.year == year and today.month == month and today.day == day_num,
                'events': day_events
            })
        calendar_weeks.append(week)

    return render_template('calendar.html', year=year, month=month, month_name=calendar.month_name[month],
                           calendar_weeks=calendar_weeks, prev_year=prev_month_date.year, prev_month=prev_month_date.month,
                           next_year=next_month_date.year, next_month=next_month_date.month)

@app.route('/export')
def export_data():
    import json
    data = {}
    for table in db.metadata.sorted_tables:
        rows = db.session.execute(table.select()).mappings().all()
        table_data = []
        for row in rows:
            row_dict = dict(row)
            for k, v in row_dict.items():
                if isinstance(v, datetime) or isinstance(v, date):
                    row_dict[k] = v.isoformat()
            table_data.append(row_dict)
        data[table.name] = table_data

    response = app.response_class(
        response=json.dumps(data, indent=2),
        status=200,
        mimetype='application/json'
    )
    response.headers["Content-Disposition"] = f"attachment; filename=gtd_backup_{get_local_now().strftime('%Y%m%d_%H%M%S')}.json"
    return response

@app.route('/import', methods=['POST'])
def import_data():
    import json
    if 'backup_file' not in request.files:
        flash('No file uploaded.', 'danger')
        return redirect(url_for('dashboard'))

    file = request.files['backup_file']
    if file.filename == '':
        flash('No file selected.', 'danger')
        return redirect(url_for('dashboard'))

    try:
        data = json.load(file)
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())

        for table in db.metadata.sorted_tables:
            if table.name in data and data[table.name]:
                records = []
                for row in data[table.name]:
                    parsed_row = {}
                    for col in table.columns:
                        val = row.get(col.name)
                        if val and isinstance(col.type, db.DateTime):
                            val = datetime.fromisoformat(val)
                        parsed_row[col.name] = val
                    records.append(parsed_row)
                db.session.execute(table.insert(), records)

        db.session.commit()
        flash('Data restored successfully!', 'success')

        user = User.query.first()
        if user:
            session['user_id'] = user.id
            session['household_id'] = user.household_id
            log_activity(user.id, 'system_restore', 'Restored database from JSON backup.')

    except Exception as e:
        db.session.rollback()
        flash(f'Error restoring data: {str(e)}', 'danger')

    return redirect(url_for('dashboard'))

@app.route('/admin/purge', methods=['POST'])
def admin_purge():
    user = db.session.get(User, session.get('user_id'))
    if user and user.role == 'admin':
        cutoff = get_local_now() - timedelta(days=30)
        items_deleted = ListItem.query.filter(ListItem.is_deleted == True, ListItem.deleted_at <= cutoff).delete()
        lists_deleted = HouseholdList.query.filter(HouseholdList.is_deleted == True, HouseholdList.deleted_at <= cutoff).delete()
        db.session.commit()
        log_activity(user.id, 'admin_purge', f"Hard purged {lists_deleted} lists and {items_deleted} items.")
        flash(f'Purge complete: {lists_deleted} lists and {items_deleted} items permanently removed.', 'success')
    else:
        flash('Unauthorized access.', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/lists')
def manage_lists():
    hid = session.get('household_id')
    q = request.args.get('q', '').strip()
    tag = request.args.get('tag', '').strip()
    sort_by = request.args.get('sort', 'newest')

    unassigned_items = ListItem.query.filter_by(household_id=hid, list_id=None, is_deleted=False).order_by(ListItem.sort_order).all()

    query = HouseholdList.query.filter_by(household_id=hid, is_deleted=False)

    if q:
        query = query.filter((HouseholdList.name.contains(q)) | (HouseholdList.description.contains(q)))
    if tag:
        query = query.filter(HouseholdList.tags.contains(tag))

    if sort_by == 'newest':
        query = query.order_by(HouseholdList.created_at.desc())
    elif sort_by == 'oldest':
        query = query.order_by(HouseholdList.created_at.asc())
    elif sort_by == 'name':
        query = query.order_by(HouseholdList.name.asc())

    lists = query.all()
    return render_template('lists.html', lists=lists, unassigned_items=unassigned_items)

@app.route('/lists/create', methods=['POST'])
def create_list():
    hid = session.get('household_id')
    new_list = HouseholdList(
        household_id=hid,
        owner_id=session['user_id'],
        name=request.form.get('name'),
        description=request.form.get('description'),
        tags=request.form.get('tags'),
        location_context=request.form.get('location_context')
    )
    db.session.add(new_list)
    db.session.commit()
    return redirect(url_for('view_list', id=new_list.id))

@app.route('/lists/<int:id>')
def view_list(id):
    household_list = db.session.get(HouseholdList, id)
    if household_list.is_deleted:
        flash("This list has been deleted.", "danger")
        return redirect(url_for('manage_lists'))
    return render_template('list_detail.html', household_list=household_list)

@app.route('/lists/<int:id>/edit', methods=['POST'])
def edit_list(id):
    household_list = db.session.get(HouseholdList, id)
    household_list.name = request.form.get('name')
    household_list.description = request.form.get('description')
    household_list.tags = request.form.get('tags')
    household_list.location_context = request.form.get('location_context')
    db.session.commit()
    flash('List updated.', 'success')
    return redirect(url_for('view_list', id=id))

@app.route('/lists/<int:id>/delete', methods=['POST'])
def delete_list(id):
    household_list = db.session.get(HouseholdList, id)
    household_list.is_deleted = True
    household_list.deleted_at = get_local_now()
    db.session.commit()
    flash(f"List '{household_list.name}' deleted.", "success")
    return redirect(url_for('manage_lists'))

@app.route('/lists/items/add_unassigned', methods=['POST'])
def add_unassigned_list_item():
    hid = session.get('household_id')
    content = request.form.get('content')
    if content:
        highest = ListItem.query.filter_by(household_id=hid, list_id=None).order_by(ListItem.sort_order.desc()).first()
        next_order = (highest.sort_order + 1) if highest else 0

        new_item = ListItem(household_id=hid, list_id=None, content=content, sort_order=next_order)
        db.session.add(new_item)
        db.session.commit()
    return redirect(url_for('manage_lists'))

@app.route('/lists/<int:id>/items', methods=['POST'])
def add_list_item(id):
    content = request.form.get('content')
    if content:
        highest = ListItem.query.filter_by(list_id=id).order_by(ListItem.sort_order.desc()).first()
        next_order = (highest.sort_order + 1) if highest else 0

        new_item = ListItem(household_id=session['household_id'], list_id=id, content=content, sort_order=next_order)
        db.session.add(new_item)
        db.session.commit()
    return redirect(url_for('view_list', id=id))

@app.route('/lists/items/<int:item_id>/toggle', methods=['POST'])
def toggle_list_item(item_id):
    item = db.session.get(ListItem, item_id)
    if item:
        item.is_checked = not item.is_checked
        db.session.commit()
        return jsonify(success=True, is_checked=item.is_checked)
    return jsonify(success=False), 404

@app.route('/lists/items/<int:item_id>/delete', methods=['POST'])
def delete_list_item(item_id):
    item = db.session.get(ListItem, item_id)
    if item:
        item.is_deleted = True
        item.deleted_at = get_local_now()
        db.session.commit()
        return jsonify(success=True)
    return jsonify(success=False), 404

@app.route('/lists/<int:id>/reorder', methods=['POST'])
def reorder_list(id):
    order_data = request.json.get('order', [])
    for data in order_data:
        item = db.session.get(ListItem, int(data['id']))
        if item and item.list_id == id:
            item.sort_order = int(data['sort_order'])
    db.session.commit()
    return jsonify(success=True)

@app.route('/lists/unassigned/reorder', methods=['POST'])
def reorder_unassigned():
    order_data = request.json.get('order', [])
    hid = session.get('household_id')
    for data in order_data:
        item = db.session.get(ListItem, int(data['id']))
        if item and item.list_id is None and item.household_id == hid:
            item.sort_order = int(data['sort_order'])
    db.session.commit()
    return jsonify(success=True)

@app.route('/assets')
def assets():
    hid = session.get('household_id')
    all_assets = Asset.query.filter_by(household_id=hid).all()
    all_supplies = Supply.query.filter_by(household_id=hid).all()
    return render_template('assets.html', assets=all_assets, all_supplies=all_supplies)

@app.route('/assets/add', methods=['POST'])
def add_asset():
    new_asset = Asset(
        household_id=session['household_id'],
        name=request.form.get('name'),
        category=request.form.get('category'),
        context=request.form.get('context'),
        power_source=request.form.get('power_source'),
        battery_type=request.form.get('battery_type'),
        battery_lifespan_days=int(request.form.get('battery_lifespan_days')) if request.form.get('battery_lifespan_days') else None,
        purchase_url=request.form.get('purchase_url'),
        notes=request.form.get('notes')
    )
    supply_ids = request.form.getlist('supplies')
    new_asset.supplies = Supply.query.filter(Supply.id.in_(supply_ids)).all()

    db.session.add(new_asset)
    db.session.commit()
    log_activity(session.get('user_id'), 'add_asset', f"Added asset: {new_asset.name}")
    return redirect(url_for('assets'))

@app.route('/assets/<int:id>')
def asset_detail(id):
    asset = db.session.get(Asset, id)
    expenses = Expense.query.filter_by(asset_id=id).order_by(Expense.date.desc()).all()
    all_supplies = Supply.query.filter_by(household_id=session.get('household_id')).all()

    total_cost = sum(e.amount for e in expenses)
    maint_cost = sum(e.amount for e in expenses if e.is_maintenance)

    return render_template('asset_detail.html', asset=asset, expenses=expenses, total_cost=total_cost, maint_cost=maint_cost, all_supplies=all_supplies)

@app.route('/assets/<int:id>/update_supplies', methods=['POST'])
def update_asset_supplies(id):
    asset = db.session.get(Asset, id)
    supply_ids = request.form.getlist('supplies')
    asset.supplies = Supply.query.filter(Supply.id.in_(supply_ids)).all()
    db.session.commit()
    flash(f"Updated linked supplies for {asset.name}.", "success")
    return redirect(url_for('asset_detail', id=id))

@app.route('/assets/<int:id>/toggle', methods=['POST'])
def asset_toggle_status(id):
    asset = db.session.get(Asset, id)
    if asset.status == 'available':
        asset.status = 'checked_out'
        asset.checked_out_by_id = session.get('user_id')
        asset.checked_out_at = get_local_now()
        log_activity(session.get('user_id'), 'checkout_asset', f"Checked out: {asset.name}")
    else:
        asset.status = 'available'
        asset.checked_out_by_id = None
        log_activity(session.get('user_id'), 'checkin_asset', f"Returned: {asset.name}")
    db.session.commit()
    return redirect(url_for('asset_detail', id=id))

@app.route('/assets/<int:asset_id>/add_schedule', methods=['POST'])
def add_maintenance_schedule(asset_id):
    sched = MaintenanceSchedule(
        asset_id=asset_id,
        name=request.form.get('name'),
        frequency_days=int(request.form.get('frequency_days')),
        next_due=get_local_now() + timedelta(days=int(request.form.get('frequency_days')))
    )
    db.session.add(sched)
    db.session.commit()
    return redirect(url_for('asset_detail', id=asset_id))

@app.route('/assets/<int:asset_id>/log_maintenance/<int:sched_id>', methods=['POST'])
def log_maintenance(asset_id, sched_id):
    sched = db.session.get(MaintenanceSchedule, sched_id)
    amount = float(request.form.get('amount'))
    desc = request.form.get('description') or f"Completed {sched.name}"

    db.session.add(Expense(asset_id=asset_id, amount=amount, description=desc, is_maintenance=True, maintenance_schedule_id=sched.id))

    sched.last_completed = get_local_now()
    sched.next_due = get_local_now() + timedelta(days=sched.frequency_days)

    db.session.commit()
    log_activity(session.get('user_id'), 'logged_maintenance', f"Performed {sched.name} on Asset #{asset_id}")
    return redirect(url_for('asset_detail', id=asset_id))

@app.route('/assets/<int:id>/expense', methods=['POST'])
def add_asset_expense(id):
    db.session.add(Expense(asset_id=id, amount=float(request.form.get('amount')), description=request.form.get('description'), is_maintenance=False))
    db.session.commit()
    return redirect(url_for('asset_detail', id=id))

@app.route('/supplies')
def supplies():
    hid = session.get('household_id')
    items = Supply.query.filter_by(household_id=hid).all()
    return render_template('supplies.html', supplies=items)

@app.route('/supplies/add', methods=['POST'])
def add_supply():
    auto_add = 'auto_add_to_shopping' in request.form
    add_now = 'add_to_list_now' in request.form

    new_supply = Supply(
        household_id=session['household_id'],
        name=request.form.get('name'),
        quantity=int(request.form.get('quantity') or 1),
        reorder_threshold=int(request.form.get('threshold') or 0),
        context=request.form.get('context'),
        purchase_url=request.form.get('purchase_url'),
        store_name=request.form.get('store_name'),
        auto_add_to_shopping=auto_add
    )
    db.session.add(new_supply)
    db.session.flush()

    if add_now:
        content = f"Buy: {new_supply.name}"
        if new_supply.store_name:
            content += f" ({new_supply.store_name})"

        highest = ListItem.query.filter_by(household_id=session['household_id'], list_id=None).order_by(ListItem.sort_order.desc()).first()
        next_order = (highest.sort_order + 1) if highest else 0

        db.session.add(ListItem(household_id=session['household_id'], list_id=None, content=content, sort_order=next_order))

    db.session.commit()
    log_activity(session.get('user_id'), 'add_supply', f"Added supply: {new_supply.name}")
    return redirect(url_for('supplies'))

@app.route('/supplies/<int:id>/use', methods=['POST'])
def use_supply(id):
    supply = db.session.get(Supply, id)
    if supply.quantity > 0:
        supply.quantity -= 1
        if supply.quantity <= supply.reorder_threshold:
            if supply.auto_add_to_shopping:
                content = f"Restock: {supply.name}"
                if supply.store_name:
                    content += f" ({supply.store_name})"

                highest = ListItem.query.filter_by(household_id=session['household_id'], list_id=None).order_by(ListItem.sort_order.desc()).first()
                next_order = (highest.sort_order + 1) if highest else 0

                db.session.add(ListItem(household_id=session['household_id'], list_id=None, content=content, sort_order=next_order))
            else:
                db.session.add(ActionItem(household_id=session['household_id'], title=f"Buy: {supply.name}", item_type='errand'))
    db.session.commit()
    return redirect(url_for('supplies'))

@app.route('/users')
def manage_users():
    return render_template('users.html')

@app.route('/users/add', methods=['POST'])
def add_user():
    hid = session.get('household_id')
    new_user = User(
        household_id=hid,
        name=request.form.get('name'),
        weekday_capacity_points=int(request.form.get('weekday') or 20),
        weekend_capacity_points=int(request.form.get('weekend') or 30),
        role='member'
    )
    db.session.add(new_user)
    db.session.commit()
    log_activity(session.get('user_id'), 'add_user', f"Added member: {new_user.name}")
    flash(f"Added new member: {new_user.name}", "success")
    return redirect(url_for('manage_users'))

@app.route('/users/<int:id>/edit', methods=['POST'])
def edit_user(id):
    u = db.session.get(User, id)
    if u:
        old_name = u.name
        u.name = request.form.get('name')
        u.weekday_capacity_points = int(request.form.get('weekday') or 20)
        u.weekend_capacity_points = int(request.form.get('weekend') or 30)
        db.session.commit()
        log_activity(session.get('user_id'), 'edit_user', f"Updated member details for: {old_name}")
        flash(f"Updated user: {u.name}", "success")
    return redirect(url_for('manage_users'))

@app.route('/switch_user', methods=['POST'])
def switch_user():
    user = db.session.get(User, request.form.get('user_id'))
    if user:
        session['user_id'] = user.id
        session['household_id'] = user.household_id
    return redirect(request.referrer or url_for('kanban'))

if __name__ == '__main__':
    with app.app_context():
        setup_db()
    app.run(host='0.0.0.0', port=5000, debug=True)