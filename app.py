import os
import calendar
from datetime import datetime, date, timedelta
from flask import Flask, request, redirect, url_for, session, flash, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from jinja2 import DictLoader

# Dependencies: pip install Flask Flask-SQLAlchemy

# ==========================================
# 1. APP CONFIGURATION
# ==========================================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'lan-local-secret-key-m0dify-in-prod'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gtd.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==========================================
# 2. DATABASE MODELS
# ==========================================
class Household(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(20), default='member') # admin, member
    weekday_capacity_points = db.Column(db.Integer, default=20)
    weekend_capacity_points = db.Column(db.Integer, default=30)
    
class InboxItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False)
    captured_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    title = db.Column(db.String(200), nullable=False)
    context = db.Column(db.String(100), nullable=True)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
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
    title = db.Column(db.String(200), nullable=False)
    context = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    item_type = db.Column(db.String(20), default='task') # task, chore, errand
    status = db.Column(db.String(20), default='ready') # ready, in_progress, blocked, done, waiting, someday
    complexity_fib = db.Column(db.Integer, default=1)
    base_points = db.Column(db.Integer, default=10)
    owner_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True) 
    
    # Recurrence Fields
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
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

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
    
    # Power & Battery Tracking
    power_source = db.Column(db.String(50)) # Battery, Wall Plug, Gas, Manual
    battery_type = db.Column(db.String(50)) # e.g. "USB-C", "AA", "12V Car Battery"
    battery_lifespan_days = db.Column(db.Integer, nullable=True) # Estimated days

    maintenance_schedules = db.relationship('MaintenanceSchedule', backref='asset', lazy=True)
    expenses = db.relationship('Expense', backref='asset_rel', lazy=True)
    supplies = db.relationship('Supply', secondary=asset_supply, backref=db.backref('assets', lazy=True))

class MaintenanceSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False) # e.g. "Oil Change", "Replace Battery"
    frequency_days = db.Column(db.Integer, nullable=False)
    last_completed = db.Column(db.DateTime, nullable=True)
    next_due = db.Column(db.DateTime, nullable=True)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Maintenance linkage
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

def log_activity(user_id, action_type, description):
    if user_id:
        db.session.add(ActivityLog(user_id=user_id, action_type=action_type, description=description))
        db.session.commit()

# ==========================================
# 3. HTML TEMPLATES
# ==========================================
TEMPLATES = {
    'base.html': """
    <!DOCTYPE html>
    <html lang="en" data-bs-theme="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>GTD Household</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            :root { --bs-body-bg: #0f1111; }
            .kanban-col { min-height: 70vh; background: #161919; border-radius: 12px; padding: 12px; transition: all 0.2s; }
            .kanban-card { cursor: grab; margin-bottom: 12px; background: #212529; border: 1px solid #373b3e; }
            .kanban-card:active { cursor: grabbing; opacity: 0.8; }
            .drag-over { border: 2px dashed #0d6efd; background: rgba(13, 110, 253, 0.05); }
            .navbar { background-color: #161919 !important; border-bottom: 1px solid #373b3e; }
            .card-hover:hover { border-color: #0d6efd !important; cursor: pointer; }
            .cal-day { height: 120px; border: 1px solid #373b3e; background: #161919; overflow-y: auto; padding: 4px; }
            .cal-day.today { background: #1a1e21; border-color: #0d6efd; }
            .cal-day.other-month { opacity: 0.3; }
            .cal-event { font-size: 0.75rem; padding: 2px 4px; border-radius: 4px; margin-bottom: 2px; cursor: pointer; display: block; text-decoration: none; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
        </style>
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-dark mb-4">
            <div class="container-fluid">
                <a class="navbar-brand fw-bold text-primary" href="{{ url_for('kanban') }}">GTD Household</a>
                <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navMain">
                    <span class="navbar-toggler-icon"></span>
                </button>
                <div class="collapse navbar-collapse" id="navMain">
                    <ul class="navbar-nav me-auto">
                        <li class="nav-item"><a class="nav-link" href="{{ url_for('dashboard') }}">Dashboard</a></li>
                        <li class="nav-item"><a class="nav-link" href="{{ url_for('calendar_view') }}">Calendar</a></li>
                        <li class="nav-item"><a class="nav-link" href="{{ url_for('kanban') }}">Board</a></li>
                        <li class="nav-item"><a class="nav-link" href="{{ url_for('inbox') }}">Inbox</a></li>
                        <li class="nav-item"><a class="nav-link" href="{{ url_for('assets') }}">Assets</a></li>
                        <li class="nav-item"><a class="nav-link" href="{{ url_for('supplies') }}">Supplies</a></li>
                        <li class="nav-item"><a class="nav-link text-info" href="{{ url_for('review') }}">Review</a></li>
                    </ul>
                    <form class="d-flex align-items-center" action="{{ url_for('switch_user') }}" method="POST">
                        <span class="text-muted small me-2">User:</span>
                        <select name="user_id" class="form-select form-select-sm bg-dark text-light border-secondary" onchange="this.form.submit()">
                            {% for u in all_users %}
                                <option value="{{ u.id }}" {% if current_user and u.id == current_user.id %}selected{% endif %}>{{ u.name }}</option>
                            {% endfor %}
                        </select>
                    </form>
                </div>
            </div>
        </nav>
        <div class="container-fluid px-4">
            {% with messages = get_flashed_messages(with_categories=true) %}
              {% if messages %}
                {% for category, message in messages %}
                  <div class="alert alert-{{ 'success' if category == 'message' else category }} alert-dismissible fade show" role="alert">
                    {{ message }}
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                  </div>
                {% endfor %}
              {% endif %}
            {% endwith %}
            {% block content %}{% endblock %}
        </div>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
        {% block scripts %}{% endblock %}
    </body>
    </html>
    """,
    'calendar.html': """
    {% extends "base.html" %}
    {% block content %}
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2 class="h4 mb-0">{{ month_name }} {{ year }}</h2>
        <div>
            <a href="{{ url_for('calendar_view', year=prev_year, month=prev_month) }}" class="btn btn-outline-secondary btn-sm">&larr; Prev</a>
            <a href="{{ url_for('calendar_view') }}" class="btn btn-outline-primary btn-sm">Today</a>
            <a href="{{ url_for('calendar_view', year=next_year, month=next_month) }}" class="btn btn-outline-secondary btn-sm">Next &rarr;</a>
        </div>
    </div>
    <div class="table-responsive">
        <div class="row g-0 text-center border-bottom border-secondary mb-1">
            <div class="col py-2 fw-bold text-muted small">SUN</div>
            <div class="col py-2 fw-bold text-muted small">MON</div>
            <div class="col py-2 fw-bold text-muted small">TUE</div>
            <div class="col py-2 fw-bold text-muted small">WED</div>
            <div class="col py-2 fw-bold text-muted small">THU</div>
            <div class="col py-2 fw-bold text-muted small">FRI</div>
            <div class="col py-2 fw-bold text-muted small">SAT</div>
        </div>
        {% for week in calendar_weeks %}
        <div class="row g-0">
            {% for day in week %}
            <div class="col cal-day {{ 'today' if day.is_today }} {{ 'other-month' if not day.in_month }}">
                <div class="d-flex justify-content-between align-items-start mb-1">
                    <span class="small fw-bold {{ 'text-primary' if day.is_today else 'text-muted' }}">{{ day.day_num }}</span>
                </div>
                {% for event in day.events %}
                    <a href="{{ url_for('edit_action', id=event.id) }}" 
                       class="cal-event bg-{{ 'info' if event.item_type == 'task' else 'warning' if event.item_type == 'chore' else 'success' }} text-dark fw-bold">
                        {% if event.is_recurring %}🔄{% endif %} {{ event.title }}
                    </a>
                {% endfor %}
            </div>
            {% endfor %}
        </div>
        {% endfor %}
    </div>
    {% endblock %}
    """,
    'kanban.html': """
    {% extends "base.html" %}
    {% block content %}
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2 class="h4 mb-0">Workflow Board</h2>
        <a href="{{ url_for('inbox') }}" class="btn btn-primary btn-sm">+ Capture Thought</a>
    </div>
    <div class="row g-3">
        {% set cols = [('ready', 'Ready', 'info'), ('in_progress', 'Doing', 'warning'), ('blocked', 'Blocked', 'danger'), ('done', 'Done', 'success')] %}
        {% for col_id, col_name, badge_color in cols %}
        <div class="col-12 col-md-3">
            <div class="p-1">
                <div class="d-flex justify-content-between align-items-center mb-2 px-1">
                    <span class="fw-bold text-uppercase small text-{{ badge_color }}">{{ col_name }}</span>
                    <span class="badge bg-dark border border-secondary text-muted">{{ items|selectattr('status', 'equalto', col_id)|list|length }}</span>
                </div>
                <div class="kanban-col" id="{{ col_id }}" ondrop="drop(event)" ondragover="allowDrop(event)" ondragleave="dragLeave(event)">
                    {% for item in items if item.status == col_id %}
                    <div class="card kanban-card shadow-sm" draggable="true" ondragstart="drag(event)" id="card-{{ item.id }}" data-id="{{ item.id }}">
                        <div class="card-body p-3">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <span class="badge bg-secondary-subtle text-secondary small text-capitalize">{{ item.item_type }}</span>
                                <span class="text-muted small">Chorenado: {{ item.complexity_fib }}</span>
                            </div>
                            <h6 class="card-title text-light mb-1">
                                <a href="{{ url_for('edit_action', id=item.id) }}" class="text-decoration-none text-info" title="Click to Edit">{{ item.title }}</a>
                            </h6>
                            <div class="small mb-1">
                                {% if item.context %}<span class="badge border border-secondary text-secondary me-1">@{{ item.context }}</span>{% endif %}
                                {% if item.due_date %}📅 {{ item.due_date.strftime('%m-%d') }}{% endif %}
                                {% if item.is_recurring %}<span class="text-info ms-2">🔄 Every {{ item.recur_interval }} {{ item.recur_unit }}</span>{% endif %}
                            </div>
                            {% if item.description %}
                                <p class="card-text text-muted small mb-1">{{ item.description[:60] }}{% if item.description|length > 60 %}...{% endif %}</p>
                            {% endif %}
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
        {% endfor %}
    </div>
    {% endblock %}
    {% block scripts %}
    <script>
        function allowDrop(ev) { ev.preventDefault(); ev.currentTarget.classList.add('drag-over'); }
        function dragLeave(ev) { ev.currentTarget.classList.remove('drag-over'); }
        function drag(ev) { ev.dataTransfer.setData("text", ev.target.id); }
        function drop(ev) {
            ev.preventDefault();
            const targetCol = ev.currentTarget;
            targetCol.classList.remove('drag-over');
            const data = ev.dataTransfer.getData("text");
            const card = document.getElementById(data);
            const newStatus = targetCol.id;
            const itemId = card.getAttribute('data-id');
            targetCol.appendChild(card);
            fetch(`/api/update_status/${itemId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: newStatus })
            }).then(res => res.json()).then(data => {
                if(!data.success) window.location.reload();
                else if (newStatus === 'done' && data.respawned) {
                    location.reload(); // Refresh to show the new recurring item
                }
            });
        }
    </script>
    {% endblock %}
    """,
    'action_edit.html': """
    {% extends "base.html" %}
    {% block content %}
    <div class="mb-3"><a href="{{ url_for('kanban') }}" class="btn btn-sm btn-outline-secondary">&larr; Back to Board</a></div>
    <div class="row justify-content-center">
        <div class="col-md-8">
            <div class="card bg-dark border-secondary shadow-sm">
                <div class="card-header border-secondary text-primary fw-bold">Edit {{ action.item_type|title }}</div>
                <div class="card-body">
                    <form action="{{ url_for('edit_action', id=action.id) }}" method="POST">
                        <div class="mb-3">
                            <label class="small text-muted">Title</label>
                            <input type="text" name="title" class="form-control bg-dark text-light border-secondary" value="{{ action.title }}" required>
                        </div>
                        <div class="row g-2 mb-3">
                            <div class="col-md-3">
                                <label class="small text-muted">Type</label>
                                <select name="item_type" class="form-select bg-dark text-light border-secondary">
                                    <option value="task" {% if action.item_type == 'task' %}selected{% endif %}>Task</option>
                                    <option value="chore" {% if action.item_type == 'chore' %}selected{% endif %}>Chore</option>
                                    <option value="errand" {% if action.item_type == 'errand' %}selected{% endif %}>Errand</option>
                                </select>
                            </div>
                            <div class="col-md-3">
                                <label class="small text-muted">Chorenado</label>
                                <select name="complexity_fib" class="form-select bg-dark text-light border-secondary">
                                    {% for val in [1, 2, 3, 5, 8, 13] %}
                                    <option value="{{ val }}" {% if action.complexity_fib == val %}selected{% endif %}>{{ val }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            <div class="col-md-3">
                                <label class="small text-muted">Context</label>
                                <input type="text" name="context" class="form-control bg-dark text-light border-secondary" value="{{ action.context or '' }}">
                            </div>
                            <div class="col-md-3">
                                <label class="small text-muted">Due Date</label>
                                <input type="date" name="due_date" class="form-control bg-dark text-light border-secondary" 
                                       value="{{ action.due_date.strftime('%Y-%m-%d') if action.due_date }}">
                            </div>
                        </div>

                        <hr class="border-secondary">
                        <h6 class="text-info mb-3 small fw-bold">Recurrence</h6>
                        <div class="row g-2 mb-3">
                            <div class="col-md-4">
                                <div class="form-check mt-4">
                                    <input class="form-check-input" type="checkbox" name="is_recurring" id="recurCheck" {% if action.is_recurring %}checked{% endif %}>
                                    <label class="form-check-label small" for="recurCheck">Recurring Event</label>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <label class="small text-muted">Interval</label>
                                <input type="number" name="recur_interval" class="form-control bg-dark text-light border-secondary" value="{{ action.recur_interval or 1 }}">
                            </div>
                            <div class="col-md-4">
                                <label class="small text-muted">Unit</label>
                                <select name="recur_unit" class="form-select bg-dark text-light border-secondary">
                                    <option value="days" {% if action.recur_unit == 'days' %}selected{% endif %}>Days</option>
                                    <option value="weeks" {% if action.recur_unit == 'weeks' %}selected{% endif %}>Weeks</option>
                                    <option value="months" {% if action.recur_unit == 'months' %}selected{% endif %}>Months</option>
                                </select>
                            </div>
                        </div>

                        <div class="mb-3">
                            <label class="small text-muted">Description & Notes</label>
                            <textarea name="description" class="form-control bg-dark text-light border-secondary" rows="3">{{ action.description or '' }}</textarea>
                        </div>

                        <hr class="border-secondary my-4">
                        <h6 class="text-info mb-3">Associated Entities</h6>
                        <div class="row g-3 mb-4">
                            <div class="col-md-6">
                                <label class="small text-muted">Linked Assets</label>
                                <select name="assets" class="form-select bg-dark text-light border-secondary" multiple size="5">
                                    {% for asset in all_assets %}
                                        <option value="{{ asset.id }}" {% if asset in action.assets %}selected{% endif %}>{{ asset.name }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            <div class="col-md-6">
                                <label class="small text-muted">Required Supplies</label>
                                <select name="supplies" class="form-select bg-dark text-light border-secondary" multiple size="5">
                                    {% for supply in all_supplies %}
                                        <option value="{{ supply.id }}" {% if supply in action.supplies %}selected{% endif %}>{{ supply.name }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                        </div>
                        
                        <div class="d-flex justify-content-end">
                            <button type="submit" class="btn btn-success px-4">Save Changes</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
    {% endblock %}
    """,
    'inbox.html': """
    {% extends "base.html" %}
    {% block content %}
    <div class="row">
        <div class="col-lg-4">
            <div class="card bg-dark border-secondary shadow mb-4">
                <div class="card-header border-secondary p-0">
                    <ul class="nav nav-tabs card-header-tabs m-0" style="border-bottom: none;">
                        <li class="nav-item"><button class="nav-link active text-primary fw-bold" data-bs-toggle="tab" data-bs-target="#single" type="button">Single Item</button></li>
                        <li class="nav-item"><button class="nav-link text-primary fw-bold" data-bs-toggle="tab" data-bs-target="#bulk" type="button">Bulk Dump</button></li>
                    </ul>
                </div>
                <div class="card-body">
                    <div class="tab-content">
                        <!-- Single Capture Tab -->
                        <div class="tab-pane fade show active" id="single">
                            <form action="{{ url_for('add_inbox') }}" method="POST">
                                <div class="mb-3">
                                    <label class="form-label small text-muted">What's on your mind?</label>
                                    <input type="text" name="title" class="form-control bg-dark text-light border-secondary" placeholder="Fix leaky faucet..." required autofocus>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label small text-muted">Context (Optional)</label>
                                    <input type="text" name="context" class="form-control bg-dark text-light border-secondary" placeholder="e.g. Garage, Kitchen, PC">
                                </div>
                                <div class="mb-3">
                                    <label class="form-label small text-muted">Details (Optional)</label>
                                    <textarea name="note" class="form-control bg-dark text-light border-secondary" rows="3"></textarea>
                                </div>
                                <button type="submit" class="btn btn-primary w-100">Capture to Inbox</button>
                            </form>
                        </div>
                        
                        <!-- Bulk Capture Tab -->
                        <div class="tab-pane fade" id="bulk">
                            <form action="{{ url_for('add_inbox_bulk') }}" method="POST">
                                <div class="mb-3">
                                    <label class="form-label small text-muted">Items (One per line)</label>
                                    <textarea name="bulk_items" class="form-control bg-dark text-light border-secondary" rows="6" placeholder="Sweep floor&#10;Organize workbench&#10;Check oil in mower" required></textarea>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label small text-muted">Apply Context to All</label>
                                    <input type="text" name="context" class="form-control bg-dark text-light border-secondary" placeholder="e.g. Garage">
                                </div>
                                <button type="submit" class="btn btn-warning w-100 text-dark fw-bold">Bulk Capture</button>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div class="col-lg-8">
            <h4 class="mb-3">Unprocessed Inbox <span class="badge bg-primary rounded-pill small">{{ inbox_items|length }}</span></h4>
            <div class="list-group">
                {% for item in inbox_items %}
                <div class="list-group-item bg-dark border-secondary text-light mb-2 rounded shadow-sm">
                    <div class="d-flex w-100 justify-content-between align-items-start">
                        <div>
                            <h5 class="mb-1 h6">
                                {{ item.title }}
                                {% if item.context %}<span class="badge border border-info text-info ms-2 small">@{{ item.context }}</span>{% endif %}
                            </h5>
                            <p class="mb-2 text-muted small">{{ item.note or '' }}</p>
                            <button type="button" class="btn btn-sm btn-outline-success px-3" data-bs-toggle="modal" data-bs-target="#processModal{{ item.id }}">Process</button>
                        </div>
                        <small class="text-muted">{{ item.created_at.strftime('%H:%M') }}</small>
                    </div>
                </div>
                <div class="modal fade" id="processModal{{ item.id }}" tabindex="-1">
                  <div class="modal-dialog">
                    <div class="modal-content bg-dark text-light border-secondary">
                      <form action="{{ url_for('process_inbox', item_id=item.id) }}" method="POST">
                          <div class="modal-header border-secondary"><h5 class="modal-title">Clarify Item</h5><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div>
                          <div class="modal-body">
                            <div class="mb-3"><label class="small text-muted">Title</label><input type="text" name="title" class="form-control bg-dark text-light border-secondary" value="{{ item.title }}" required></div>
                            <div class="row g-2 mb-3">
                                <div class="col-4"><label class="small text-muted">Type</label>
                                    <select name="item_type" class="form-select bg-dark text-light border-secondary">
                                        <option value="task">Task</option><option value="chore">Chore</option><option value="errand">Errand</option>
                                    </select>
                                </div>
                                <div class="col-4"><label class="small text-muted">Chorenado</label>
                                    <select name="complexity_fib" class="form-select bg-dark text-light border-secondary">
                                        <option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="5">5</option>
                                    </select>
                                </div>
                                <div class="col-4"><label class="small text-muted">Context</label>
                                    <input type="text" name="context" class="form-control bg-dark text-light border-secondary" value="{{ item.context or '' }}">
                                </div>
                            </div>
                            <div class="row g-2 mb-3">
                                <div class="col-6"><label class="small text-muted">Due Date</label><input type="date" name="due_date" class="form-control bg-dark text-light border-secondary"></div>
                                <div class="col-6"><label class="small text-muted">Recur Every</label>
                                    <div class="input-group">
                                        <input type="number" name="recur_interval" class="form-control bg-dark text-light border-secondary" placeholder="0">
                                        <select name="recur_unit" class="form-select bg-dark text-light border-secondary">
                                            <option value="days">Days</option><option value="weeks">Weeks</option><option value="months">Months</option>
                                        </select>
                                    </div>
                                </div>
                            </div>
                            <div class="mb-3"><label class="small text-muted">Description</label><textarea name="description" class="form-control bg-dark text-light border-secondary" rows="3">{{ item.note }}</textarea></div>
                          </div>
                          <div class="modal-footer border-secondary"><button type="submit" class="btn btn-success w-100">Move to Board</button></div>
                      </form>
                    </div>
                  </div>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>
    {% endblock %}
    """,
    'dashboard.html': """
    {% extends "base.html" %}
    {% block content %}
    <h2 class="mb-4">Dashboard</h2>
    <div class="row">
        <div class="col-md-4">
            <div class="card bg-dark border-secondary shadow-sm mb-4">
                <div class="card-body text-center">
                    <h5 class="text-muted small fw-bold">COMPLETED TODAY</h5>
                    <h1 class="display-3 text-success">{{ today_completions }}</h1>
                </div>
            </div>
            
            <!-- Data Management Card -->
            <div class="card bg-dark border-secondary shadow-sm mb-4">
                <div class="card-header border-secondary text-info small fw-bold">DATA MANAGEMENT</div>
                <div class="card-body">
                    <p class="text-muted small mb-3">Backup or restore your household data in JSON format.</p>
                    <a href="{{ url_for('export_data') }}" class="btn btn-sm btn-outline-info w-100 mb-3">Export JSON Backup</a>
                    <form action="{{ url_for('import_data') }}" method="POST" enctype="multipart/form-data">
                        <label class="text-muted small mb-1">Restore from Backup:</label>
                        <div class="input-group input-group-sm">
                            <input type="file" name="backup_file" class="form-control bg-dark text-light border-secondary" accept=".json" required>
                            <button class="btn btn-danger" type="submit" onclick="return confirm('WARNING: This will erase all current data and replace it with the backup. Continue?');">Restore</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
        <div class="col-md-8">
            <div class="card bg-dark border-secondary shadow-sm">
                <div class="card-header border-secondary text-primary small fw-bold">RECENT ACTIVITY</div>
                <ul class="list-group list-group-flush">
                    {% for log in activity %}
                    <li class="list-group-item bg-dark text-light border-secondary d-flex justify-content-between">
                        <span><span class="badge bg-secondary me-2">{{ log.action_type|replace('_', ' ')|title }}</span> {{ log.description }}</span>
                        <small class="text-muted">{{ log.timestamp.strftime('%H:%M') }}</small>
                    </li>
                    {% endfor %}
                </ul>
            </div>
        </div>
    </div>
    {% endblock %}
    """,
    'assets.html': """
    {% extends "base.html" %}
    {% block content %}
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2 class="h4 mb-0">Assets</h2>
        <button class="btn btn-primary btn-sm" data-bs-toggle="modal" data-bs-target="#addAssetModal">+ Add Asset</button>
    </div>
    <div class="row g-3">
        {% for asset in assets %}
        <div class="col-md-4">
            <a href="{{ url_for('asset_detail', id=asset.id) }}" class="text-decoration-none">
                <div class="card bg-dark border-secondary shadow-sm h-100 card-hover">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start mb-2">
                            <h5 class="card-title text-light mb-0">{{ asset.name }}</h5>
                            <span class="badge {{ 'bg-warning text-dark' if asset.status == 'checked_out' else 'bg-success' }}">{{ asset.status|replace('_',' ')|title }}</span>
                        </div>
                        <p class="text-muted small mb-1">{{ asset.category|title }} | {{ asset.context }}</p>
                        {% if asset.power_source %}
                            <span class="badge border border-secondary text-muted small">🔌 {{ asset.power_source }}</span>
                        {% endif %}
                    </div>
                </div>
            </a>
        </div>
        {% endfor %}
    </div>

    <!-- Add Asset Modal -->
    <div class="modal fade" id="addAssetModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content bg-dark text-light border-secondary">
                <form action="{{ url_for('add_asset') }}" method="POST">
                    <div class="modal-header border-secondary"><h5 class="modal-title">Register New Asset</h5><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div>
                    <div class="modal-body">
                        <div class="mb-3"><label class="small text-muted">Asset Name</label><input type="text" name="name" class="form-control bg-dark text-light border-secondary" required></div>
                        <div class="row g-2 mb-3">
                            <div class="col-6"><label class="small text-muted">Category</label><input type="text" name="category" class="form-control bg-dark text-light border-secondary" placeholder="Vehicle, Electronics..."></div>
                            <div class="col-6"><label class="small text-muted">Context (Location)</label><input type="text" name="context" class="form-control bg-dark text-light border-secondary" placeholder="Garage, Kitchen..."></div>
                        </div>
                        <hr class="border-secondary">
                        <h6 class="small text-info fw-bold">Power & Battery Tracking</h6>
                        <div class="row g-2 mb-3">
                            <div class="col-4"><label class="small text-muted">Power Source</label>
                                <select name="power_source" class="form-select bg-dark text-light border-secondary">
                                    <option value="">N/A</option><option value="Battery">Battery</option><option value="Wall Plug">Wall Plug</option><option value="Gas">Gasoline</option>
                                </select>
                            </div>
                            <div class="col-4"><label class="small text-muted">Battery Type</label><input type="text" name="battery_type" class="form-control bg-dark text-light border-secondary" placeholder="USB-C, AA, 12V..."></div>
                            <div class="col-4"><label class="small text-muted">Lifespan (Days)</label><input type="number" name="battery_lifespan_days" class="form-control bg-dark text-light border-secondary" placeholder="365"></div>
                        </div>
                        <hr class="border-secondary">
                        <div class="mb-3"><label class="small text-muted">Purchase/Info URL</label><input type="url" name="purchase_url" class="form-control bg-dark text-light border-secondary" placeholder="https://amazon.com/..."></div>
                        <div class="mb-3">
                            <label class="small text-muted">Linked Supplies (Optional)</label>
                            <select name="supplies" class="form-select bg-dark text-light border-secondary" multiple size="3">
                                {% for s in all_supplies %}
                                    <option value="{{ s.id }}">{{ s.name }} ({{ s.quantity }})</option>
                                {% endfor %}
                            </select>
                            <div class="form-text text-muted small">Hold Ctrl/Cmd to select multiple.</div>
                        </div>
                    </div>
                    <div class="modal-footer border-secondary"><button class="btn btn-success w-100">Add Asset</button></div>
                </form>
            </div>
        </div>
    </div>
    {% endblock %}
    """,
    'asset_detail.html': """
    {% extends "base.html" %}
    {% block content %}
    <div class="mb-3"><a href="{{ url_for('assets') }}" class="btn btn-sm btn-outline-secondary">&larr; Back to Assets</a></div>
    
    <!-- Cost of Ownership Dashboard (Top Row) -->
    <div class="row mb-4">
        <div class="col-md-4">
            <div class="card bg-dark border-secondary shadow-sm h-100">
                <div class="card-body">
                    <h3 class="text-light mb-1">{{ asset.name }}</h3>
                    <div class="mb-3">
                        <span class="badge bg-primary me-1">{{ asset.category|title }}</span>
                        <span class="badge bg-secondary">{{ asset.context }}</span>
                    </div>
                    {% if asset.power_source %}
                        <p class="small text-muted mb-1"><strong>Power:</strong> {{ asset.power_source }} {% if asset.battery_type %}({{ asset.battery_type }}){% endif %}</p>
                    {% endif %}
                    {% if asset.purchase_url %}
                        <a href="{{ asset.purchase_url }}" target="_blank" class="btn btn-sm btn-outline-info w-100 mb-3">🔗 Purchase / Docs Link</a>
                    {% endif %}
                    <form action="{{ url_for('asset_toggle_status', id=asset.id) }}" method="POST" class="mb-3">
                        <button type="submit" class="btn {{ 'btn-success' if asset.status != 'available' else 'btn-warning' }} w-100 btn-sm">
                            {{ 'Check In' if asset.status != 'available' else 'Check Out' }}
                        </button>
                    </form>
                    
                    <hr class="border-secondary">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="text-info fw-bold small">REQUIRED SUPPLIES</span>
                        <button class="btn btn-sm btn-outline-info py-0 px-1" data-bs-toggle="modal" data-bs-target="#linkSuppliesModal">+</button>
                    </div>
                    {% for s in asset.supplies %}
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <span class="small text-light">{{ s.name }}</span>
                            <span class="badge {{ 'bg-danger' if s.quantity <= s.reorder_threshold else 'bg-success' }}">{{ s.quantity }} in stock</span>
                        </div>
                    {% else %}
                        <p class="small text-muted mb-0">No supplies linked.</p>
                    {% endfor %}
                </div>
            </div>
        </div>
        <div class="col-md-8">
            <div class="card bg-dark border-secondary shadow-sm h-100">
                <div class="card-header border-secondary text-primary small fw-bold">COST OF OWNERSHIP DASHBOARD</div>
                <div class="card-body">
                    <div class="row text-center">
                        <div class="col-4 border-end border-secondary">
                            <p class="text-muted small mb-1">TOTAL SPEND</p>
                            <h2 class="text-light">${{ "%.2f"|format(total_cost) }}</h2>
                        </div>
                        <div class="col-4 border-end border-secondary">
                            <p class="text-muted small mb-1">MAINTENANCE</p>
                            <h2 class="text-warning">${{ "%.2f"|format(maint_cost) }}</h2>
                        </div>
                        <div class="col-4">
                            <p class="text-muted small mb-1">OTHER (GAS/MISC)</p>
                            <h2 class="text-info">${{ "%.2f"|format(total_cost - maint_cost) }}</h2>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Maintenance and Expenses (Bottom Row) -->
    <div class="row">
        <!-- Maintenance Schedules -->
        <div class="col-md-6 mb-4">
            <div class="card bg-dark border-secondary shadow-sm h-100">
                <div class="card-header border-secondary d-flex justify-content-between align-items-center">
                    <span class="text-warning fw-bold">Maintenance Schedules</span> 
                    <button class="btn btn-sm btn-outline-warning" data-bs-toggle="modal" data-bs-target="#maintModal">+ Add Schedule</button>
                </div>
                <div class="card-body p-0">
                    <ul class="list-group list-group-flush">
                        {% for schedule in asset.maintenance_schedules %}
                        <li class="list-group-item bg-dark text-light border-secondary py-3">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <strong>{{ schedule.name }}</strong>
                                <span class="badge {{ 'bg-danger' if schedule.next_due and schedule.next_due.date() <= today else 'bg-secondary' }}">
                                    Due: {{ schedule.next_due.strftime('%Y-%m-%d') if schedule.next_due else 'Not scheduled' }}
                                </span>
                            </div>
                            <div class="d-flex justify-content-between align-items-center">
                                <small class="text-muted">Every {{ schedule.frequency_days }} days | Last: {{ schedule.last_completed.strftime('%Y-%m-%d') if schedule.last_completed else 'Never' }}</small>
                                <button class="btn btn-sm btn-success" data-bs-toggle="modal" data-bs-target="#logMaintModal{{ schedule.id }}">Log Done</button>
                            </div>
                        </li>
                        
                        <!-- Log Maintenance Completion Modal -->
                        <div class="modal fade" id="logMaintModal{{ schedule.id }}" tabindex="-1">
                            <div class="modal-dialog"><div class="modal-content bg-dark text-light border-secondary">
                                <form action="{{ url_for('log_maintenance', asset_id=asset.id, sched_id=schedule.id) }}" method="POST">
                                    <div class="modal-header border-secondary"><h5 class="modal-title">Log: {{ schedule.name }}</h5><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div>
                                    <div class="modal-body">
                                        <p class="small text-muted mb-3">Logging this will recalculate the next due date and add an entry to the Expense History.</p>
                                        <div class="mb-2"><label class="small text-muted">Cost of Maintenance ($)</label><input type="number" step="0.01" name="amount" class="form-control bg-dark text-light border-secondary" required></div>
                                        <div><label class="small text-muted">Notes / Details</label><input type="text" name="description" class="form-control bg-dark text-light border-secondary" placeholder="e.g., Synthetic Oil, Replaced battery cell"></div>
                                    </div>
                                    <div class="modal-footer border-secondary"><button class="btn btn-success w-100">Record Completion</button></div>
                                </form>
                            </div></div>
                        </div>
                        {% else %}
                        <li class="list-group-item bg-dark text-muted py-4 text-center">No maintenance schedules tracked.</li>
                        {% endfor %}
                    </ul>
                </div>
            </div>
        </div>

        <!-- Expense Ledger -->
        <div class="col-md-6 mb-4">
            <div class="card bg-dark border-secondary shadow-sm h-100">
                <div class="card-header border-secondary d-flex justify-content-between align-items-center">
                    <span class="text-info fw-bold">Expense History</span> 
                    <button class="btn btn-sm btn-outline-info" data-bs-toggle="modal" data-bs-target="#expModal">+ Log Expense</button>
                </div>
                <div class="card-body p-0" style="max-height: 400px; overflow-y: auto;">
                    <table class="table table-dark table-striped mb-0">
                        <thead><tr><th>Date</th><th>Description</th><th class="text-end">Amount</th></tr></thead>
                        <tbody>
                            {% for exp in expenses %}
                            <tr>
                                <td class="small">{{ exp.date.strftime('%Y-%m-%d') }}</td>
                                <td class="small">
                                    {% if exp.is_maintenance %}<span class="badge bg-warning text-dark me-1" title="Maintenance Event">🔧</span>{% endif %}
                                    {{ exp.description }}
                                </td>
                                <td class="text-end text-danger small">-${{ "%.2f"|format(exp.amount) }}</td>
                            </tr>
                            {% else %}
                            <tr><td colspan="3" class="text-center text-muted py-4">No expenses yet.</td></tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <!-- Link Supplies Modal -->
    <div class="modal fade" id="linkSuppliesModal" tabindex="-1">
        <div class="modal-dialog"><div class="modal-content bg-dark text-light border-secondary">
            <form action="{{ url_for('update_asset_supplies', id=asset.id) }}" method="POST">
                <div class="modal-header border-secondary"><h5 class="modal-title">Link Supplies to {{ asset.name }}</h5><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div>
                <div class="modal-body">
                    <select name="supplies" class="form-select bg-dark text-light border-secondary" multiple size="8">
                        {% for s in all_supplies %}
                            <option value="{{ s.id }}" {% if s in asset.supplies %}selected{% endif %}>{{ s.name }} ({{ s.quantity }} left)</option>
                        {% endfor %}
                    </select>
                    <div class="form-text text-muted small mt-2">Hold Ctrl/Cmd to select multiple.</div>
                </div>
                <div class="modal-footer border-secondary"><button class="btn btn-success w-100">Save Linked Supplies</button></div>
            </form>
        </div></div>
    </div>

    <!-- Create Maintenance Schedule Modal -->
    <div class="modal fade" id="maintModal" tabindex="-1">
        <div class="modal-dialog"><div class="modal-content bg-dark text-light border-secondary">
            <form action="{{ url_for('add_maintenance_schedule', asset_id=asset.id) }}" method="POST">
                <div class="modal-header border-secondary"><h5 class="modal-title">New Maintenance Schedule</h5><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div>
                <div class="modal-body">
                    <div class="mb-3"><label class="small text-muted">Task Name</label><input type="text" name="name" class="form-control bg-dark text-light border-secondary" placeholder="Oil Change, Battery Replacement" required></div>
                    <div class="mb-3"><label class="small text-muted">Frequency (Days)</label><input type="number" name="frequency_days" class="form-control bg-dark text-light border-secondary" placeholder="180" required></div>
                </div>
                <div class="modal-footer border-secondary"><button class="btn btn-warning w-100">Create Schedule</button></div>
            </form>
        </div></div>
    </div>

    <!-- Generic Expense Modal -->
    <div class="modal fade" id="expModal" tabindex="-1">
        <div class="modal-dialog"><div class="modal-content bg-dark text-light border-secondary">
            <form action="{{ url_for('add_asset_expense', id=asset.id) }}" method="POST">
                <div class="modal-header border-secondary"><h5 class="modal-title">Log General Expense</h5><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div>
                <div class="modal-body">
                    <div class="mb-2"><label class="small text-muted">Amount ($)</label><input type="number" step="0.01" name="amount" class="form-control bg-dark text-light border-secondary" required></div>
                    <div><label class="small text-muted">Description</label><input type="text" name="description" class="form-control bg-dark text-light border-secondary" placeholder="Gas, Accessories..." required></div>
                </div>
                <div class="modal-footer border-secondary"><button class="btn btn-info w-100">Save Expense</button></div>
            </form>
        </div></div>
    </div>
    {% endblock %}
    """,
    'supplies.html': """
    {% extends "base.html" %}
    {% block content %}
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2 class="h4 mb-0">Supplies</h2>
        <button class="btn btn-primary btn-sm" data-bs-toggle="modal" data-bs-target="#addSupplyModal">+ Add</button>
    </div>
    <div class="row g-3">
        {% for supply in supplies %}
        <div class="col-md-3">
            <div class="card bg-dark border-secondary p-3 text-center shadow-sm h-100">
                <h6>{{ supply.name }}</h6>
                <p class="text-muted small mb-1">{{ supply.context or 'General' }}</p>
                <h2 class="{{ 'text-danger' if supply.quantity <= supply.reorder_threshold else 'text-success' }}">{{ supply.quantity }}</h2>
                <div class="d-grid gap-2">
                    <form action="{{ url_for('use_supply', id=supply.id) }}" method="POST"><button class="btn btn-sm btn-outline-info w-100">Use</button></form>
                    {% if supply.purchase_url %}
                        <a href="{{ supply.purchase_url }}" target="_blank" class="btn btn-sm btn-link text-info text-decoration-none small">Buy More</a>
                    {% endif %}
                </div>
            </div>
        </div>
        {% endfor %}
    </div>

    <!-- Add Supply Modal -->
    <div class="modal fade" id="addSupplyModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content bg-dark text-light border-secondary">
                <form action="{{ url_for('add_supply') }}" method="POST">
                    <div class="modal-header border-secondary"><h5 class="modal-title">New Supply Item</h5><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div>
                    <div class="modal-body">
                        <div class="mb-3"><label class="small text-muted">Item Name</label><input type="text" name="name" class="form-control bg-dark text-light border-secondary" required></div>
                        <div class="row g-2 mb-3">
                            <div class="col-6"><label class="small text-muted">Initial Qty</label><input type="number" name="quantity" class="form-control bg-dark text-light border-secondary" value="1"></div>
                            <div class="col-6"><label class="small text-muted">Reorder Threshold</label><input type="number" name="threshold" class="form-control bg-dark text-light border-secondary" value="1"></div>
                        </div>
                        <div class="mb-3"><label class="small text-muted">Context (Location)</label><input type="text" name="context" class="form-control bg-dark text-light border-secondary" placeholder="Kitchen, Garage..."></div>
                        <div class="mb-3"><label class="small text-muted">Purchase URL</label><input type="url" name="purchase_url" class="form-control bg-dark text-light border-secondary" placeholder="https://amazon.com/..."></div>
                    </div>
                    <div class="modal-footer border-secondary"><button class="btn btn-success w-100">Add Supply</button></div>
                </form>
            </div>
        </div>
    </div>
    {% endblock %}
    """,
    'review.html': """
    {% extends "base.html" %}
    {% block content %}
    <div class="text-center py-4"><h2 class="text-info fw-bold mb-4">Weekly Review</h2>
        <div class="row justify-content-center">
            <div class="col-md-6">
                <div class="card bg-dark border-secondary text-start p-4 mb-3 shadow">
                    <h5 class="text-primary">Inbox ({{ inbox_count }})</h5>
                    <a href="{{ url_for('inbox') }}" class="btn btn-sm btn-primary px-4">Process</a>
                </div>
                <div class="card bg-dark border-secondary text-start p-4 mb-3 shadow">
                    <h5 class="text-warning">Waiting On</h5>
                    <ul class="list-group list-group-flush">
                        {% for item in waiting_items %}
                        <li class="list-group-item bg-dark text-light border-secondary small">{{ item.title }}</li>
                        {% else %}
                        <li class="list-group-item bg-dark text-muted border-secondary small">No pending items.</li>
                        {% endfor %}
                    </ul>
                </div>
                <div class="card bg-dark border-secondary text-start p-4 mb-3 shadow">
                    <h5 class="text-info">Active Recurring Chores</h5>
                    <ul class="list-group list-group-flush">
                        {% for item in recurring_items %}
                        <li class="list-group-item bg-dark text-light border-secondary small d-flex justify-content-between align-items-center">
                            <span><a href="{{ url_for('edit_action', id=item.id) }}" class="text-info text-decoration-none">{{ item.title }}</a></span>
                            <span class="badge bg-secondary">Every {{ item.recur_interval }} {{ item.recur_unit }}</span>
                        </li>
                        {% else %}
                        <li class="list-group-item bg-dark text-muted border-secondary small">No recurring items setup.</li>
                        {% endfor %}
                    </ul>
                </div>
            </div>
        </div>
    </div>
    {% endblock %}
    """
}
app.jinja_loader = DictLoader(TEMPLATES)

# ==========================================
# 4. UTILS & MIDDLEWARE
# ==========================================
@app.context_processor
def inject_global_data():
    current_user_id = session.get('user_id')
    current_user = db.session.get(User, current_user_id) if current_user_id else None
    all_users = User.query.all()
    return dict(current_user=current_user, all_users=all_users, today=date.today())

@app.before_request
def check_setup():
    if not hasattr(app, '_setup_done'):
        db.create_all()
        if not Household.query.first():
            h = Household(name="Local Household")
            db.session.add(h)
            db.session.commit()
            u1 = User(name="Admin", role="admin", household_id=h.id)
            u2 = User(name="Member", role="member", household_id=h.id)
            db.session.add_all([u1, u2])
            db.session.commit()
            
            # Seed Initial Assets and Supplies
            drone = Asset(household_id=h.id, name="Drone Kit", category="electronics", context="Office", power_source="Battery", battery_type="Proprietary Lipo", battery_lifespan_days=365)
            vw = Asset(household_id=h.id, name="VW Wagen", category="vehicle", context="Garage", power_source="Gas")
            cleaner = Supply(household_id=h.id, name="Toilet Cleaner", quantity=1, reorder_threshold=0, context="Kitchen pantry")
            
            # New specific supplies for VW Wagen
            oil = Supply(household_id=h.id, name="Synthetic Oil 5W-30", quantity=2, reorder_threshold=1, context="Garage")
            oil_filter = Supply(household_id=h.id, name="Oil Filter", quantity=1, reorder_threshold=0, context="Garage")
            
            db.session.add_all([drone, vw, cleaner, oil, oil_filter])
            vw.supplies.extend([oil, oil_filter])
            
            db.session.commit()

            # Seed Maintenance Schedules
            vw_oil = MaintenanceSchedule(asset_id=vw.id, name="Synthetic Oil Change", frequency_days=180, next_due=datetime.utcnow() + timedelta(days=30))
            drone_bat = MaintenanceSchedule(asset_id=drone.id, name="Replace Battery", frequency_days=365, next_due=datetime.utcnow() - timedelta(days=5)) # Overdue example
            db.session.add_all([vw_oil, drone_bat])
            db.session.commit()

        app._setup_done = True

    if 'user_id' not in session and request.endpoint not in ['static', None]:
        first_user = User.query.first()
        if first_user:
            session['user_id'] = first_user.id
            session['household_id'] = first_user.household_id

def calculate_next_due_date(current_date, interval, unit):
    if not current_date:
        current_date = datetime.utcnow()
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
@app.route('/')
def kanban():
    hid = session.get('household_id')
    items = ActionItem.query.filter_by(household_id=hid).order_by(ActionItem.created_at.desc()).all()
    return render_template('kanban.html', items=items)

@app.route('/calendar')
@app.route('/calendar/<int:year>/<int:month>')
def calendar_view(year=None, month=None):
    today = date.today()
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
                day_events = [a for a in actions if a.due_date.date() == current_dt]
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

    action = ActionItem(
        household_id=session['household_id'], 
        title=request.form.get('title'),
        description=request.form.get('description'), 
        item_type=request.form.get('item_type'),
        complexity_fib=int(request.form.get('complexity_fib')), 
        context=request.form.get('context'),
        owner_user_id=session['user_id'],
        due_date=due_date,
        is_recurring=is_recurring,
        recur_interval=int(interval) if is_recurring else 1,
        recur_unit=request.form.get('recur_unit') if is_recurring else 'days'
    )
    db.session.add(action)
    inbox_item.processed_at = datetime.utcnow()
    db.session.commit()
    flash("Action added.", "success")
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
        action.is_recurring = 'is_recurring' in request.form
        action.recur_interval = int(request.form.get('recur_interval') or 1)
        action.recur_unit = request.form.get('recur_unit')
        
        due_date_str = request.form.get('due_date')
        action.due_date = datetime.strptime(due_date_str, '%Y-%m-%d') if due_date_str else None
        
        # Handle Many-to-Many Associations
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
            action.completed_at = datetime.utcnow()
            log_activity(session.get('user_id'), 'completed_task', f"Finished: {action.title}")
            
            if action.is_recurring:
                new_due = calculate_next_due_date(action.due_date or datetime.utcnow(), action.recur_interval, action.recur_unit)
                new_action = ActionItem(
                    household_id=action.household_id,
                    title=action.title,
                    description=action.description,
                    item_type=action.item_type,
                    complexity_fib=action.complexity_fib,
                    context=action.context,
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

@app.route('/switch_user', methods=['POST'])
def switch_user():
    user = db.session.get(User, request.form.get('user_id'))
    if user:
        session['user_id'] = user.id
        session['household_id'] = user.household_id
    return redirect(request.referrer or url_for('kanban'))

@app.route('/dashboard')
def dashboard():
    today = datetime.utcnow().date()
    activity = ActivityLog.query.filter(ActivityLog.timestamp >= today).order_by(ActivityLog.timestamp.desc()).all()
    completions = ActionItem.query.filter(ActionItem.completed_at >= today).count()
    return render_template('dashboard.html', activity=activity, today_completions=completions)

@app.route('/export')
def export_data():
    import json
    data = {}
    
    # Iterate through all tables defined in SQLAlchemy
    for table in db.metadata.sorted_tables:
        rows = db.session.execute(table.select()).mappings().all()
        table_data = []
        for row in rows:
            row_dict = dict(row)
            # Serialize dates to ISO format strings
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
    # Force download as attachment
    response.headers["Content-Disposition"] = f"attachment; filename=gtd_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
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
        
        # 1. Clear existing data in reverse dependency order (avoids foreign key constraint errors)
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
            
        # 2. Insert new data in forward dependency order
        for table in db.metadata.sorted_tables:
            if table.name in data and data[table.name]:
                records = []
                for row in data[table.name]:
                    parsed_row = {}
                    for col in table.columns:
                        val = row.get(col.name)
                        # Convert ISO strings back to datetime objects
                        if val and isinstance(col.type, db.DateTime):
                            val = datetime.fromisoformat(val)
                        parsed_row[col.name] = val
                    records.append(parsed_row)
                db.session.execute(table.insert(), records)
                
        db.session.commit()
        flash('Data restored successfully!', 'success')
        
        # Re-fetch user session details to prevent lockout after ID resets
        user = User.query.first()
        if user:
            session['user_id'] = user.id
            session['household_id'] = user.household_id
            log_activity(user.id, 'system_restore', 'Restored database from JSON backup.')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error restoring data: {str(e)}', 'danger')
        
    return redirect(url_for('dashboard'))

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
        asset.checked_out_at = datetime.utcnow()
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
        next_due=datetime.utcnow() + timedelta(days=int(request.form.get('frequency_days')))
    )
    db.session.add(sched)
    db.session.commit()
    return redirect(url_for('asset_detail', id=asset_id))

@app.route('/assets/<int:asset_id>/log_maintenance/<int:sched_id>', methods=['POST'])
def log_maintenance(asset_id, sched_id):
    sched = db.session.get(MaintenanceSchedule, sched_id)
    amount = float(request.form.get('amount'))
    desc = request.form.get('description') or f"Completed {sched.name}"
    
    # Log Expense
    db.session.add(Expense(asset_id=asset_id, amount=amount, description=desc, is_maintenance=True, maintenance_schedule_id=sched.id))
    
    # Update Schedule
    sched.last_completed = datetime.utcnow()
    sched.next_due = datetime.utcnow() + timedelta(days=sched.frequency_days)
    
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
    new_supply = Supply(household_id=session['household_id'], name=request.form.get('name'), quantity=int(request.form.get('quantity') or 1),
                        reorder_threshold=int(request.form.get('threshold') or 0), context=request.form.get('context'),
                        purchase_url=request.form.get('purchase_url'))
    db.session.add(new_supply)
    db.session.commit()
    log_activity(session.get('user_id'), 'add_supply', f"Added supply: {new_supply.name}")
    return redirect(url_for('supplies'))

@app.route('/supplies/<int:id>/use', methods=['POST'])
def use_supply(id):
    supply = db.session.get(Supply, id)
    if supply.quantity > 0:
        supply.quantity -= 1
        if supply.quantity <= supply.reorder_threshold:
            db.session.add(ActionItem(household_id=session['household_id'], title=f"Buy: {supply.name}", item_type='errand'))
    db.session.commit()
    return redirect(url_for('supplies'))

@app.route('/review')
def review():
    hid = session.get('household_id')
    inbox_count = InboxItem.query.filter_by(household_id=hid, processed_at=None).count()
    waiting = ActionItem.query.filter_by(household_id=hid, status='waiting').all()
    
    # Get all recurring items, but filter out historical 'done' ones so we only see the active pending cycle
    recurring = ActionItem.query.filter_by(household_id=hid, is_recurring=True).all()
    active_recurring = [item for item in recurring if item.status != 'done']

    return render_template('review.html', inbox_count=inbox_count, waiting_items=waiting, recurring_items=active_recurring)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
