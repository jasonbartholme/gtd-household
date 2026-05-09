import os
import calendar
from datetime import datetime, date, timedelta
from flask import Flask, request, redirect, url_for, session, flash, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from jinja2 import DictLoader
from zoneinfo import ZoneInfo

# ==========================================
# 1. APP CONFIGURATION
# ==========================================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'lan-local-secret-key-m0dify-in-prod'
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
# 3. HTML TEMPLATES
# ==========================================
TEMPLATES = {
    'base.html': """
    <!DOCTYPE html>
    <html lang="en" data-bs-theme="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{% if page_title %}{{ page_title }} - {% endif %}GTD Household</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            :root { --bs-body-bg: #0f1111; }
            .kanban-col { min-height: 70vh; background: #161919; border-radius: 12px; padding: 12px; transition: all 0.2s; }
            .kanban-card { cursor: grab; margin-bottom: 12px; background: #212529; border: 1px solid #373b3e; }
            .kanban-card:active { cursor: grabbing; opacity: 0.8; }
            .drag-over { border: 2px dashed #0d6efd; background: rgba(13, 110, 253, 0.05); }
            /* Updated Navbar with CSS Texture */
            .navbar { 
                background-color: #161919 !important; 
                background-image: radial-gradient(#373b3e 1px, transparent 1px);
                background-size: 16px 16px;
                border-bottom: 1px solid #373b3e; 
            }
            .dropdown-menu-dark { background-color: #161919; border-color: #373b3e; }
            .card-hover:hover { border-color: #0d6efd !important; cursor: pointer; }
            .cal-day { height: 120px; border: 1px solid #373b3e; background: #161919; overflow-y: auto; padding: 4px; }
            .cal-day.today { background: #1a1e21; border-color: #0d6efd; }
            .cal-day.other-month { opacity: 0.3; }
            .cal-event { font-size: 0.75rem; padding: 2px 4px; border-radius: 4px; margin-bottom: 2px; cursor: pointer; display: block; text-decoration: none; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
            .list-item-row.checked .list-content { text-decoration: line-through; opacity: 0.6; }
            .drag-handle { cursor: grab; padding: 0 10px; color: #6c757d; }
            .drag-handle:active { cursor: grabbing; }
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
                        <!-- Workflow Dropdown -->
                        <li class="nav-item dropdown">
                            <a class="nav-link dropdown-toggle {% if request.endpoint in ['kanban', 'inbox', 'review'] %}active{% endif %}" href="#" role="button" data-bs-toggle="dropdown">
                                Workflow {% if unproc_inbox > 0 %}<span class="badge bg-danger rounded-pill ms-1">{{ unproc_inbox }}</span>{% endif %}
                            </a>
                            <ul class="dropdown-menu dropdown-menu-dark">
                                <li><a class="dropdown-item" href="{{ url_for('kanban') }}">Board</a></li>
                                <li><a class="dropdown-item" href="{{ url_for('inbox') }}">Inbox {% if unproc_inbox > 0 %}<span class="badge bg-danger rounded-pill float-end">{{ unproc_inbox }}</span>{% endif %}</a></li>
                                <li><a class="dropdown-item text-primary" href="{{ url_for('review') }}">Review</a></li>
                            </ul>
                        </li>
                        
                        <!-- Planning Dropdown -->
                        <li class="nav-item dropdown">
                            <a class="nav-link dropdown-toggle {% if request.endpoint in ['manage_projects', 'manage_lists', 'calendar_view', 'someday_view'] %}active{% endif %}" href="#" role="button" data-bs-toggle="dropdown">Planning</a>
                            <ul class="dropdown-menu dropdown-menu-dark">
                                <li><a class="dropdown-item" href="{{ url_for('manage_projects') }}">Projects</a></li>
                                <li><a class="dropdown-item" href="{{ url_for('manage_lists') }}">Lists</a></li>
                                <li><a class="dropdown-item" href="{{ url_for('calendar_view') }}">Calendar</a></li>
                                <li><hr class="dropdown-divider"></li>
                                <li><a class="dropdown-item text-secondary" href="{{ url_for('someday_view') }}">Someday/Maybe</a></li>
                            </ul>
                        </li>

                        <!-- Household Dropdown -->
                        <li class="nav-item dropdown">
                            <a class="nav-link dropdown-toggle {% if request.endpoint in ['supplies', 'assets'] %}active{% endif %}" href="#" role="button" data-bs-toggle="dropdown">Household</a>
                            <ul class="dropdown-menu dropdown-menu-dark">
                                <li><a class="dropdown-item" href="{{ url_for('supplies') }}">Supplies</a></li>
                                <li><a class="dropdown-item" href="{{ url_for('assets') }}">Assets</a></li>
                            </ul>
                        </li>

                        <!-- Metrics Dropdown -->
                        <li class="nav-item dropdown">
                            <a class="nav-link dropdown-toggle {% if request.endpoint in ['dashboard', 'leaderboard'] %}active{% endif %}" href="#" role="button" data-bs-toggle="dropdown">Metrics</a>
                            <ul class="dropdown-menu dropdown-menu-dark">
                                <li><a class="dropdown-item" href="{{ url_for('dashboard') }}">Dashboard</a></li>
                                <li><a class="dropdown-item text-warning" href="{{ url_for('leaderboard') }}">Leaderboard 🏆</a></li>
                            </ul>
                        </li>
                    </ul>
                    <form class="d-flex align-items-center" action="{{ url_for('switch_user') }}" method="POST">
                        <span class="text-muted small me-2">User:</span>
                        <select name="user_id" class="form-select form-select-sm bg-dark text-light border-secondary" onchange="this.form.submit()">
                            {% for u in all_users %}
                                <option value="{{ u.id }}" {% if current_user and u.id == current_user.id %}selected{% endif %}>{{ u.name }}</option>
                            {% endfor %}
                        </select>
                        <a href="{{ url_for('manage_users') }}" class="btn btn-sm btn-outline-secondary ms-2" title="Manage Users">⚙️</a>
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
        <script src="https://cdn.jsdelivr.net/npm/sortablejs@latest/Sortable.min.js"></script>
        <script>
            document.addEventListener("DOMContentLoaded", function(){
                var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
                var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
                    return new bootstrap.Tooltip(tooltipTriggerEl)
                })
            });
        </script>
        {% block scripts %}{% endblock %}
    </body>
    </html>
    """,
    'kanban.html': """
    {% extends "base.html" %}

    {% macro render_kanban_card(item) %}
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
                {% if item.project %}<span class="badge border border-primary text-primary me-1">📁 {{ item.project.name }}</span>{% endif %}
                {% if item.context %}<span class="badge border border-secondary text-secondary me-1">@{{ item.context }}</span>{% endif %}
                {% if item.due_date %}📅 {{ item.due_date.strftime('%m-%d') }}{% endif %}
                {% if item.is_recurring %}<span class="text-info ms-2">🔄 Every {{ item.recur_interval }} {{ item.recur_unit }}</span>{% endif %}
            </div>
            {% if item.description %}
                <p class="card-text text-muted small mb-1">{{ item.description[:60] }}{% if item.description|length > 60 %}...{% endif %}</p>
            {% endif %}
        </div>
    </div>
    {% endmacro %}

    {% block content %}
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2 class="h4 mb-0">Workflow Board</h2>
        <a href="{{ url_for('inbox') }}" class="btn btn-primary btn-sm">+ Capture Thought</a>
    </div>
    <div class="row g-3">
        {% set cols = [('ready', 'Ready', 'info', 'Next Actions: Physical, visible actions you can take right now without waiting.'), ('in_progress', 'Doing', 'warning', 'Work in Progress: Limit this to maintain focus.'), ('blocked', 'Blocked', 'danger', 'Waiting On: Tasks stalled pending input from someone or something else.'), ('done', 'Done', 'success', 'Archived completions. Good job!')] %}
        {% for col_id, col_name, badge_color, tooltip in cols %}
        <div class="col-12 col-md-3">
            <div class="p-1">
                <div class="d-flex justify-content-between align-items-center mb-2 px-1">
                    <span class="fw-bold text-uppercase small text-{{ badge_color }}" data-bs-toggle="tooltip" title="{{ tooltip }}" style="cursor: help;">{{ col_name }} ℹ️</span>
                    <span class="badge bg-dark border border-secondary text-muted">{{ items|selectattr('status', 'equalto', col_id)|list|length }}</span>
                </div>
                <div class="kanban-col" id="{{ col_id }}" ondrop="drop(event)" ondragover="allowDrop(event)" ondragleave="dragLeave(event)">
                    
                    {% if col_id == 'ready' %}
                        <!-- Kanban Filters for Ready Column -->
                        <div class="mb-3 d-flex gap-1 flex-wrap kanban-filters">
                            <button class="btn btn-sm py-0 px-2 btn-outline-secondary active filter-btn" onclick="filterReady('all', this)">All</button>
                            <button class="btn btn-sm py-0 px-2 btn-outline-info filter-btn" onclick="filterReady('recurring', this)">Recurring</button>
                            <button class="btn btn-sm py-0 px-2 btn-outline-primary filter-btn" onclick="filterReady('projects', this)">Projects</button>
                            <button class="btn btn-sm py-0 px-2 btn-outline-warning filter-btn" onclick="filterReady('errands', this)">Errands</button>
                        </div>

                        {% set ready_items = items|selectattr('status', 'equalto', 'ready')|list %}
                        
                        <div class="ready-group" data-group="recurring">
                            {% set rec_items = ready_items|selectattr('is_recurring', 'equalto', true)|list %}
                            {% if rec_items %}
                                <div class="text-muted small fw-bold mt-2 mb-2 border-bottom border-secondary pb-1">Recurring Items</div>
                                {% for item in rec_items %} {{ render_kanban_card(item) }} {% endfor %}
                            {% endif %}
                        </div>

                        <div class="ready-group" data-group="projects">
                            {% set proj_items = ready_items|selectattr('is_recurring', 'equalto', false)|rejectattr('project_id', 'none')|list %}
                            {% if proj_items %}
                                <div class="text-muted small fw-bold mt-3 mb-2 border-bottom border-secondary pb-1">Project Actions</div>
                                {% for item in proj_items %} {{ render_kanban_card(item) }} {% endfor %}
                            {% endif %}
                        </div>

                        <div class="ready-group" data-group="errands">
                            {% set err_items = ready_items|selectattr('is_recurring', 'equalto', false)|selectattr('project_id', 'none')|selectattr('item_type', 'equalto', 'errand')|list %}
                            {% if err_items %}
                                <div class="text-muted small fw-bold mt-3 mb-2 border-bottom border-secondary pb-1">Errands & Shopping</div>
                                {% for item in err_items %} {{ render_kanban_card(item) }} {% endfor %}
                            {% endif %}
                        </div>

                        <div class="ready-group" data-group="tasks">
                            {% set task_items = ready_items|selectattr('is_recurring', 'equalto', false)|selectattr('project_id', 'none')|rejectattr('item_type', 'equalto', 'errand')|list %}
                            {% if task_items %}
                                <div class="text-muted small fw-bold mt-3 mb-2 border-bottom border-secondary pb-1">Tasks & Chores</div>
                                {% for item in task_items %} {{ render_kanban_card(item) }} {% endfor %}
                            {% endif %}
                        </div>

                    {% else %}
                        <!-- Standard loop for Doing, Blocked, Done -->
                        {% for item in items if item.status == col_id %}
                            {{ render_kanban_card(item) }}
                        {% endfor %}
                    {% endif %}
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
                    location.reload(); 
                }
            });
        }

        // Kanban Filter Logic
        function filterReady(type, btnElement) {
            // Update Active State on Buttons
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            btnElement.classList.add('active');

            // Show/Hide Groups
            document.querySelectorAll('.ready-group').forEach(group => {
                if (type === 'all' || group.dataset.group === type) {
                    group.style.display = 'block';
                } else {
                    group.style.display = 'none';
                }
            });
        }
    </script>
    {% endblock %}
    """,
    'projects.html': """
    {% extends "base.html" %}
    {% block content %}
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2 class="h4 mb-0 text-info fw-bold" data-bs-toggle="tooltip" title="GTD Rule: Any outcome that requires more than one step is a Project. Keep them here, and put their next physical action on the Kanban board!" style="cursor: help;">Active Projects ℹ️</h2>
        <button class="btn btn-primary btn-sm" data-bs-toggle="modal" data-bs-target="#addProjectModal">+ New Project</button>
    </div>
    <div class="row g-3">
        {% for proj in projects %}
        <div class="col-md-6">
            <div class="card bg-dark border-secondary shadow-sm h-100 card-hover">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <h5 class="card-title text-light mb-0"><a href="{{ url_for('project_detail', id=proj.id) }}" class="text-decoration-none text-info">{{ proj.name }}</a></h5>
                        <span class="badge {{ 'bg-success' if proj.status == 'completed' else 'bg-primary' }}">{{ proj.status|title }}</span>
                    </div>
                    <p class="text-muted small mb-3">{{ proj.description[:100] if proj.description else 'No description provided.' }}</p>
                    
                    {% set total_actions = proj.actions|length %}
                    {% set done_actions = proj.actions|selectattr('status', 'equalto', 'done')|list|length %}
                    {% set percent = (done_actions / total_actions * 100)|round|int if total_actions > 0 else 0 %}
                    
                    <div class="d-flex justify-content-between align-items-center small text-muted mb-1">
                        <span>Progress</span>
                        <span>{{ done_actions }} / {{ total_actions }} Tasks</span>
                    </div>
                    <div class="progress" style="height: 6px; background-color: #373b3e;">
                        <div class="progress-bar bg-info" role="progressbar" style="width: {{ percent }}%;"></div>
                    </div>
                </div>
            </div>
        </div>
        {% else %}
        <div class="col-12 text-center py-5">
            <h5 class="text-muted">No active projects.</h5>
            <p class="text-muted small">Got a big goal? Break it down into a Project!</p>
        </div>
        {% endfor %}
    </div>

    <!-- Add Project Modal -->
    <div class="modal fade" id="addProjectModal" tabindex="-1">
        <div class="modal-dialog"><div class="modal-content bg-dark text-light border-secondary">
            <form action="{{ url_for('add_project') }}" method="POST">
                <div class="modal-header border-secondary"><h5 class="modal-title">New Project</h5><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div>
                <div class="modal-body">
                    <div class="mb-3"><label class="small text-muted">Project Name</label><input type="text" name="name" class="form-control bg-dark text-light border-secondary" required placeholder="E.g., Winterize the House"></div>
                    <div class="mb-3"><label class="small text-muted">Description & Desired Outcome</label><textarea name="description" class="form-control bg-dark text-light border-secondary" rows="3"></textarea></div>
                </div>
                <div class="modal-footer border-secondary"><button class="btn btn-success w-100">Create Project</button></div>
            </form>
        </div></div>
    </div>
    {% endblock %}
    """,
    'project_detail.html': """
    {% extends "base.html" %}
    {% block content %}
    <div class="mb-3"><a href="{{ url_for('manage_projects') }}" class="btn btn-sm btn-outline-secondary">&larr; Back to Projects</a></div>
    
    <div class="row">
        <div class="col-md-4">
            <div class="card bg-dark border-secondary shadow-sm mb-4">
                <div class="card-body">
                    <h4 class="text-info fw-bold mb-2">{{ project.name }}</h4>
                    <span class="badge {{ 'bg-success' if project.status == 'completed' else 'bg-primary' }} mb-3">{{ project.status|title }}</span>
                    <p class="text-muted small">{{ project.description }}</p>
                    <hr class="border-secondary">
                    <form action="{{ url_for('toggle_project_status', id=project.id) }}" method="POST">
                        <button type="submit" class="btn {{ 'btn-warning' if project.status == 'completed' else 'btn-success' }} w-100 btn-sm">
                            {{ 'Reopen Project' if project.status == 'completed' else 'Mark as Completed' }}
                        </button>
                    </form>
                </div>
            </div>
        </div>
        <div class="col-md-8">
            <div class="card bg-dark border-secondary shadow-sm h-100">
                <div class="card-header border-secondary text-primary small fw-bold d-flex justify-content-between align-items-center">
                    PROJECT ACTIONS
                    <a href="{{ url_for('inbox') }}" class="btn btn-sm btn-outline-primary py-0">Capture New Action</a>
                </div>
                <div class="card-body p-0">
                    <ul class="list-group list-group-flush">
                        {% for action in project.actions %}
                        <li class="list-group-item bg-dark text-light border-secondary d-flex justify-content-between align-items-center">
                            <div>
                                <a href="{{ url_for('edit_action', id=action.id) }}" class="text-decoration-none text-light fw-bold">{{ action.title }}</a>
                                {% if action.context %}<span class="badge border border-secondary text-secondary ms-2 small">@{{ action.context }}</span>{% endif %}
                            </div>
                            <span class="badge 
                                {% if action.status == 'done' %}bg-success
                                {% elif action.status == 'someday' %}bg-secondary
                                {% elif action.status == 'blocked' %}bg-danger
                                {% elif action.status == 'in_progress' %}bg-warning text-dark
                                {% else %}bg-info text-dark{% endif %}">
                                {{ action.status|replace('_', ' ')|title }}
                            </span>
                        </li>
                        {% else %}
                        <li class="list-group-item bg-dark text-muted text-center py-4">No actions associated with this project. Edit a task to assign it here!</li>
                        {% endfor %}
                    </ul>
                </div>
            </div>
        </div>
    </div>
    {% endblock %}
    """,
    'someday.html': """
    {% extends "base.html" %}
    {% block content %}
    <div class="d-flex justify-content-between align-items-center mb-4">
        <div>
            <h2 class="h4 mb-0 text-secondary fw-bold" data-bs-toggle="tooltip" title="Ideas you want to do, but not right now. Review these weekly and activate them when you have capacity." style="cursor: help;">Someday / Maybe Incubator ℹ️</h2>
            <p class="text-muted small mt-1">These items do not appear on your active Kanban board.</p>
        </div>
        <a href="{{ url_for('inbox') }}" class="btn btn-secondary btn-sm">+ Add Idea</a>
    </div>

    <div class="row g-3">
        {% for item in items %}
        <div class="col-md-4">
            <div class="card bg-dark border-secondary shadow-sm h-100">
                <div class="card-body d-flex flex-column">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <span class="badge bg-secondary-subtle text-secondary small text-capitalize">{{ item.item_type }}</span>
                        <span class="text-muted small">Fib: {{ item.complexity_fib }}</span>
                    </div>
                    <h6 class="card-title text-light mb-1">
                        <a href="{{ url_for('edit_action', id=item.id) }}" class="text-decoration-none text-light">{{ item.title }}</a>
                    </h6>
                    <div class="small mb-3">
                        {% if item.project %}<span class="badge border border-primary text-primary me-1">📁 {{ item.project.name }}</span>{% endif %}
                        {% if item.context %}<span class="badge border border-secondary text-secondary me-1">@{{ item.context }}</span>{% endif %}
                    </div>
                    {% if item.description %}
                        <p class="card-text text-muted small mb-3">{{ item.description }}</p>
                    {% endif %}
                    
                    <form action="{{ url_for('activate_someday', id=item.id) }}" method="POST" class="mt-auto">
                        <button type="submit" class="btn btn-outline-info btn-sm w-100">Activate (Move to Ready)</button>
                    </form>
                </div>
            </div>
        </div>
        {% else %}
        <div class="col-12 text-center py-5">
            <h5 class="text-muted">No incubating ideas.</h5>
            <p class="text-muted small">Got a crazy idea for the future? Send it to the Someday list from your Inbox!</p>
        </div>
        {% endfor %}
    </div>
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
                            <label class="small text-muted" data-bs-toggle="tooltip" title="Make sure this starts with a verb!" style="cursor: help;">Title ℹ️</label>
                            <input type="text" name="title" class="form-control bg-dark text-light border-secondary" value="{{ action.title }}" required>
                        </div>
                        
                        <div class="row g-2 mb-3">
                            <div class="col-md-6">
                                <label class="small text-muted" data-bs-toggle="tooltip" title="Assign this action to a larger multi-step outcome." style="cursor: help;">Project (Optional) ℹ️</label>
                                <select name="project_id" class="form-select bg-dark text-light border-secondary">
                                    <option value="">-- No Project --</option>
                                    {% for p in all_projects %}
                                    <option value="{{ p.id }}" {% if action.project_id == p.id %}selected{% endif %}>{{ p.name }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            <div class="col-md-6">
                                <label class="small text-muted" data-bs-toggle="tooltip" title="Use Someday to hide this from your active board." style="cursor: help;">Board Status ℹ️</label>
                                <select name="status" class="form-select bg-dark text-light border-secondary">
                                    <option value="ready" {% if action.status == 'ready' %}selected{% endif %}>Ready (Active Board)</option>
                                    <option value="in_progress" {% if action.status == 'in_progress' %}selected{% endif %}>Doing (Active Board)</option>
                                    <option value="blocked" {% if action.status == 'blocked' %}selected{% endif %}>Blocked (Active Board)</option>
                                    <option value="someday" {% if action.status == 'someday' %}selected{% endif %}>Someday / Maybe (Hidden)</option>
                                    <option value="done" {% if action.status == 'done' %}selected{% endif %}>Done (Archived)</option>
                                </select>
                            </div>
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
                                    <label class="form-label small text-muted" data-bs-toggle="tooltip" title="Brain Dump: Get every 'open loop' out of your head immediately." style="cursor: help;">What's on your mind? ℹ️</label>
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
                                <div class="col-6">
                                    <label class="small text-muted" data-bs-toggle="tooltip" title="Assign to a larger multi-step outcome." style="cursor: help;">Project ℹ️</label>
                                    <select name="project_id" class="form-select bg-dark text-light border-secondary">
                                        <option value="">-- No Project --</option>
                                        {% for p in all_projects %}
                                        <option value="{{ p.id }}">{{ p.name }}</option>
                                        {% endfor %}
                                    </select>
                                </div>
                                <div class="col-6">
                                    <label class="small text-muted" data-bs-toggle="tooltip" title="Ready goes to Kanban. Someday hides it." style="cursor: help;">Initial Status ℹ️</label>
                                    <select name="status" class="form-select bg-dark text-light border-secondary">
                                        <option value="ready">Ready (Active Board)</option>
                                        <option value="someday">Someday / Maybe (Incubator)</option>
                                    </select>
                                </div>
                            </div>

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
                          <div class="modal-footer border-secondary"><button type="submit" class="btn btn-success w-100">Process Action</button></div>
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
    'review.html': """
    {% extends "base.html" %}
    {% block content %}
    <div class="text-center py-4"><h2 class="text-info fw-bold mb-4" data-bs-toggle="tooltip" title="The Weekly Review is the key to GTD. Get clear, get current, and get creative. Empty your inbox and review active lists." style="cursor: help;">Weekly Review ℹ️</h2>
        <div class="row justify-content-center">
            <div class="col-md-6">
                <div class="card bg-dark border-secondary text-start p-4 mb-3 shadow">
                    <h5 class="text-primary" data-bs-toggle="tooltip" title="Process everything to zero. Decide what each item is and what the next action is." style="cursor: help;">Inbox ({{ inbox_count }}) ℹ️</h5>
                    <a href="{{ url_for('inbox') }}" class="btn btn-sm btn-primary px-4">Process</a>
                </div>
                <div class="card bg-dark border-secondary text-start p-4 mb-3 shadow">
                    <h5 class="text-secondary" data-bs-toggle="tooltip" title="Review ideas you put on hold. Are you ready to activate any of them?" style="cursor: help;">Someday / Maybe ({{ someday_count }}) ℹ️</h5>
                    <a href="{{ url_for('someday_view') }}" class="btn btn-sm btn-secondary px-4">Review Ideas</a>
                </div>
                <div class="card bg-dark border-secondary text-start p-4 mb-3 shadow">
                    <h5 class="text-warning" data-bs-toggle="tooltip" title="Review items blocked by others. Follow up with them if necessary!" style="cursor: help;">Waiting On ℹ️</h5>
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
            
            {% if current_user and current_user.role == 'admin' %}
            <div class="card bg-dark border-danger shadow-sm mb-4">
                <div class="card-header border-danger text-danger small fw-bold">ADMIN ACTIONS</div>
                <div class="card-body">
                    <div class="d-flex justify-content-between mb-2">
                        <span class="text-muted small">Total Active Lists:</span>
                        <span class="text-light fw-bold">{{ active_lists_count }}</span>
                    </div>
                    <div class="d-flex justify-content-between mb-3">
                        <span class="text-muted small" data-bs-toggle="tooltip" title="Soft-deleted items older than 30 days awaiting permanent deletion.">Pending Purge Data: ℹ️</span>
                        <span class="text-warning fw-bold">{{ purgeable_lists_count }} lists / {{ purgeable_items_count }} items</span>
                    </div>
                    {% if purgeable_lists_count > 0 or purgeable_items_count > 0 %}
                    <form action="{{ url_for('admin_purge') }}" method="POST" onsubmit="return confirm('Permanently delete stale soft-deleted data? This cannot be undone.');">
                        <button class="btn btn-sm btn-danger w-100">Execute Hard Purge</button>
                    </form>
                    {% else %}
                        <button class="btn btn-sm btn-secondary w-100" disabled>Database Clean</button>
                    {% endif %}
                </div>
            </div>
            {% endif %}
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
    'leaderboard.html': """
    {% extends "base.html" %}
    {% block content %}
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2 class="h4 mb-0 text-warning fw-bold">🏆 Chorenado Leaderboard</h2>
    </div>

    <div class="row mb-4">
        {% for tp in todays_points %}
        <div class="col-md-4 mb-3">
            <div class="card bg-dark border-warning shadow-sm h-100">
                <div class="card-body text-center">
                    <h5 class="text-muted small fw-bold">TODAY'S CHORENADO CHAMP</h5>
                    <h1 class="display-3 text-warning fw-bold">{{ tp.points }}</h1>
                    <span class="badge bg-secondary fs-6">{{ tp.name }}</span>
                </div>
            </div>
        </div>
        {% else %}
        <div class="col-12">
            <div class="card bg-dark border-secondary shadow-sm">
                <div class="card-body text-center py-5">
                    <h5 class="text-muted">No Chorenado points earned today yet!</h5>
                    <p class="text-muted small">Move some tasks to 'Done' to get on the board.</p>
                </div>
            </div>
        </div>
        {% endfor %}
    </div>

    <div class="row g-4">
        <div class="col-md-6">
            <div class="card bg-dark border-secondary shadow-sm h-100">
                <div class="card-header border-secondary text-info small fw-bold">TOP DAILY CHORENADO CHAMP POINTS</div>
                <div class="card-body p-0">
                    <table class="table table-dark table-striped mb-0">
                        <thead><tr><th>Rank</th><th>Person</th><th>Date</th><th class="text-end">Points</th></tr></thead>
                        <tbody>
                            {% for score in top_scores %}
                            <tr>
                                <td class="text-muted">#{{ loop.index }}</td>
                                <td>{{ score.name }}</td>
                                <td class="small">{{ score.date }}</td>
                                <td class="text-end text-warning fw-bold">{{ score.points }}</td>
                            </tr>
                            {% else %}
                            <tr><td colspan="4" class="text-center text-muted py-3">No data available.</td></tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <div class="col-md-6">
            <div class="card bg-dark border-secondary shadow-sm h-100">
                <div class="card-header border-secondary text-success small fw-bold">MOST RECENT CHORENADO POINTS</div>
                <div class="card-body p-0">
                    <table class="table table-dark table-striped mb-0">
                        <thead><tr><th>Person</th><th>Date</th><th class="text-end">Points</th></tr></thead>
                        <tbody>
                            {% for score in recent_scores %}
                            <tr>
                                <td>{{ score.name }}</td>
                                <td class="small">{{ score.date }}</td>
                                <td class="text-end text-success fw-bold">{{ score.points }}</td>
                            </tr>
                            {% else %}
                            <tr><td colspan="3" class="text-center text-muted py-3">No data available.</td></tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    {% endblock %}
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
    'lists.html': """
    {% extends "base.html" %}
    {% block content %}
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2 class="h4 mb-0 text-info fw-bold">Household Lists</h2>
        <button class="btn btn-primary btn-sm" data-bs-toggle="modal" data-bs-target="#createListModal">+ Create List</button>
    </div>

    <!-- General Shopping List / Unassigned Items -->
    <div class="card bg-dark border-secondary shadow-sm mb-4">
        <div class="card-header border-secondary d-flex justify-content-between align-items-center">
            <h5 class="mb-0 text-warning fw-bold">General Shopping List (Unassigned)</h5>
            <span class="badge bg-secondary-subtle text-secondary small">{{ unassigned_items|length }} items</span>
        </div>
        <div class="card-body p-0">
            <ul class="list-group list-group-flush" id="sortable-unassigned">
                {% for item in unassigned_items %}
                <li class="list-group-item bg-dark text-light border-secondary d-flex align-items-center list-item-row {{ 'checked' if item.is_checked else '' }}" data-id="{{ item.id }}">
                    <span class="drag-handle">☰</span>
                    <input class="form-check-input item-checkbox me-3 mt-0" type="checkbox" data-id="{{ item.id }}" {% if item.is_checked %}checked{% endif %} style="transform: scale(1.3); cursor: pointer;">
                    <span class="list-content flex-grow-1">{{ item.content }}</span>
                    <button class="btn btn-sm text-muted delete-item-btn" data-id="{{ item.id }}" title="Remove item">🗑️</button>
                </li>
                {% else %}
                <li class="list-group-item bg-dark text-muted text-center py-3" id="empty-unassigned">No items here. Add a quick item below!</li>
                {% endfor %}
            </ul>
        </div>
        <div class="card-footer border-secondary">
            <form action="{{ url_for('add_unassigned_list_item') }}" method="POST" class="d-flex">
                <input type="text" name="content" class="form-control bg-dark text-light border-secondary me-2" placeholder="Add a quick item..." required autocomplete="off">
                <button type="submit" class="btn btn-warning text-dark fw-bold">Add</button>
            </form>
        </div>
    </div>

    <!-- Filter & Sort Controls -->
    <div class="card bg-dark border-secondary mb-4 shadow-sm">
        <div class="card-body p-3">
            <form method="GET" action="{{ url_for('manage_lists') }}" class="row g-2 align-items-center">
                <div class="col-md-5">
                    <input type="text" name="q" class="form-control form-control-sm bg-dark text-light border-secondary" placeholder="Search lists..." value="{{ request.args.get('q', '') }}">
                </div>
                <div class="col-md-3">
                    <input type="text" name="tag" class="form-control form-control-sm bg-dark text-light border-secondary" placeholder="Filter by tag..." value="{{ request.args.get('tag', '') }}">
                </div>
                <div class="col-md-3">
                    <select name="sort" class="form-select form-select-sm bg-dark text-light border-secondary">
                        <option value="newest" {% if request.args.get('sort') == 'newest' %}selected{% endif %}>Newest First</option>
                        <option value="oldest" {% if request.args.get('sort') == 'oldest' %}selected{% endif %}>Oldest First</option>
                        <option value="name" {% if request.args.get('sort') == 'name' %}selected{% endif %}>Name (A-Z)</option>
                    </select>
                </div>
                <div class="col-md-1">
                    <button type="submit" class="btn btn-sm btn-outline-info w-100">Filter</button>
                </div>
            </form>
        </div>
    </div>

    <!-- List Cards -->
    <div class="row g-3">
        {% for list in lists %}
        <div class="col-md-4">
            <div class="card bg-dark border-secondary shadow-sm h-100 card-hover">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <h5 class="card-title text-light mb-0"><a href="{{ url_for('view_list', id=list.id) }}" class="text-decoration-none text-info">{{ list.name }}</a></h5>
                        <span class="badge bg-secondary-subtle text-secondary small">{{ list.items|rejectattr('is_deleted')|list|length }} items</span>
                    </div>
                    {% if list.location_context %}
                        <p class="text-warning small mb-2"><i class="bi bi-geo-alt"></i> @{{ list.location_context }}</p>
                    {% endif %}
                    <p class="text-muted small mb-3">{{ list.description[:100] if list.description else 'No description.' }}</p>
                    
                    <div class="d-flex justify-content-between align-items-center mt-auto">
                        <div>
                            {% if list.tags %}
                                {% for tag in list.tags.split(',') %}
                                    <span class="badge border border-secondary text-muted small">{{ tag.strip() }}</span>
                                {% endfor %}
                            {% endif %}
                        </div>
                        <small class="text-muted">By: {{ list.owner.name }}</small>
                    </div>
                </div>
            </div>
        </div>
        {% else %}
        <div class="col-12 text-center py-5">
            <h5 class="text-muted">No lists found.</h5>
            <p class="text-muted small">Create one to keep track of groceries, packing, or projects!</p>
        </div>
        {% endfor %}
    </div>

    <!-- Create List Modal -->
    <div class="modal fade" id="createListModal" tabindex="-1">
        <div class="modal-dialog"><div class="modal-content bg-dark text-light border-secondary">
            <form action="{{ url_for('create_list') }}" method="POST">
                <div class="modal-header border-secondary"><h5 class="modal-title">Create New List</h5><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div>
                <div class="modal-body">
                    <div class="mb-3"><label class="small text-muted">List Name</label><input type="text" name="name" class="form-control bg-dark text-light border-secondary" required placeholder="E.g., Menards Run"></div>
                    <div class="mb-3"><label class="small text-muted" data-bs-toggle="tooltip" title="For live shopping, link this list to a physical context.">Errand Context (Optional) ℹ️</label><input type="text" name="location_context" class="form-control bg-dark text-light border-secondary" placeholder="E.g., Hardware Store, Grocery"></div>
                    <div class="mb-3"><label class="small text-muted">Tags (Comma Separated)</label><input type="text" name="tags" class="form-control bg-dark text-light border-secondary" placeholder="home, repairs, shopping"></div>
                    <div class="mb-3"><label class="small text-muted">Description</label><textarea name="description" class="form-control bg-dark text-light border-secondary" rows="2"></textarea></div>
                </div>
                <div class="modal-footer border-secondary"><button class="btn btn-success w-100">Create List</button></div>
            </form>
        </div></div>
    </div>
    {% endblock %}
    
    {% block scripts %}
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            // Toggle Checkbox
            document.querySelectorAll('.item-checkbox').forEach(cb => {
                cb.addEventListener('change', function() {
                    const itemId = this.dataset.id;
                    const row = this.closest('.list-item-row');
                    if(this.checked) row.classList.add('checked');
                    else row.classList.remove('checked');
                    fetch(`/lists/items/${itemId}/toggle`, { method: 'POST' });
                });
            });

            // Soft Delete
            document.querySelectorAll('.delete-item-btn').forEach(btn => {
                btn.addEventListener('click', function(e) {
                    e.preventDefault();
                    const itemId = this.dataset.id;
                    const row = this.closest('.list-item-row');
                    row.style.opacity = '0';
                    setTimeout(() => row.remove(), 300);
                    fetch(`/lists/items/${itemId}/delete`, { method: 'POST' });
                });
            });

            // SortableJS Unassigned
            var elUnassigned = document.getElementById('sortable-unassigned');
            if(elUnassigned && !document.getElementById('empty-unassigned')) {
                Sortable.create(elUnassigned, {
                    handle: '.drag-handle',
                    animation: 150,
                    onEnd: function (evt) {
                        let order = [];
                        document.querySelectorAll('#sortable-unassigned .list-item-row').forEach((row, index) => {
                            order.push({ id: row.dataset.id, sort_order: index });
                        });
                        fetch(`{{ url_for('reorder_unassigned') }}`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ order: order })
                        });
                    }
                });
            }
        });
    </script>
    {% endblock %}
    """,
    'list_detail.html': """
    {% extends "base.html" %}
    {% block content %}
    <div class="mb-3"><a href="{{ url_for('manage_lists') }}" class="btn btn-sm btn-outline-secondary">&larr; Back to Lists</a></div>
    
    <div class="row justify-content-center">
        <div class="col-md-8">
            <div class="card bg-dark border-secondary shadow-sm mb-4">
                <div class="card-header border-secondary d-flex justify-content-between align-items-center">
                    <div>
                        <h4 class="text-info fw-bold mb-0 d-inline-block">{{ household_list.name }}</h4>
                        {% if household_list.location_context %}
                            <span class="badge bg-warning text-dark ms-2">@{{ household_list.location_context }}</span>
                        {% endif %}
                    </div>
                    <div class="dropdown">
                        <button class="btn btn-sm btn-outline-secondary dropdown-toggle" type="button" data-bs-toggle="dropdown">Options</button>
                        <ul class="dropdown-menu dropdown-menu-dark">
                            <li><a class="dropdown-item" href="#" data-bs-toggle="modal" data-bs-target="#editListModal">Edit List Info</a></li>
                            <li><hr class="dropdown-divider"></li>
                            <li>
                                <form action="{{ url_for('delete_list', id=household_list.id) }}" method="POST" onsubmit="return confirm('Soft-delete this entire list?');">
                                    <button class="dropdown-item text-danger" type="submit">Delete List</button>
                                </form>
                            </li>
                        </ul>
                    </div>
                </div>
                <div class="card-body p-0">
                    <ul class="list-group list-group-flush" id="sortable-list">
                        {% for item in household_list.items if not item.is_deleted %}
                        <li class="list-group-item bg-dark text-light border-secondary d-flex align-items-center list-item-row {{ 'checked' if item.is_checked else '' }}" data-id="{{ item.id }}">
                            <span class="drag-handle">☰</span>
                            <input class="form-check-input item-checkbox me-3 mt-0" type="checkbox" data-id="{{ item.id }}" {% if item.is_checked %}checked{% endif %} style="transform: scale(1.3); cursor: pointer;">
                            <span class="list-content flex-grow-1">{{ item.content }}</span>
                            <button class="btn btn-sm text-muted delete-item-btn" data-id="{{ item.id }}" title="Remove item">🗑️</button>
                        </li>
                        {% else %}
                        <li class="list-group-item bg-dark text-muted text-center py-4" id="empty-state">This list is empty.</li>
                        {% endfor %}
                    </ul>
                </div>
                <div class="card-footer border-secondary">
                    <form action="{{ url_for('add_list_item', id=household_list.id) }}" method="POST" class="d-flex">
                        <input type="text" name="content" class="form-control bg-dark text-light border-secondary me-2" placeholder="Add an item..." required autocomplete="off">
                        <button type="submit" class="btn btn-primary">Add</button>
                    </form>
                </div>
            </div>
        </div>
    </div>

    <!-- Edit List Modal -->
    <div class="modal fade" id="editListModal" tabindex="-1">
        <div class="modal-dialog"><div class="modal-content bg-dark text-light border-secondary">
            <form action="{{ url_for('edit_list', id=household_list.id) }}" method="POST">
                <div class="modal-header border-secondary"><h5 class="modal-title">Edit List</h5><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div>
                <div class="modal-body">
                    <div class="mb-3"><label class="small text-muted">List Name</label><input type="text" name="name" class="form-control bg-dark text-light border-secondary" value="{{ household_list.name }}" required></div>
                    <div class="mb-3"><label class="small text-muted">Errand Context</label><input type="text" name="location_context" class="form-control bg-dark text-light border-secondary" value="{{ household_list.location_context or '' }}"></div>
                    <div class="mb-3"><label class="small text-muted">Tags (Comma Separated)</label><input type="text" name="tags" class="form-control bg-dark text-light border-secondary" value="{{ household_list.tags or '' }}"></div>
                    <div class="mb-3"><label class="small text-muted">Description</label><textarea name="description" class="form-control bg-dark text-light border-secondary" rows="2">{{ household_list.description or '' }}</textarea></div>
                </div>
                <div class="modal-footer border-secondary"><button class="btn btn-success w-100">Save Changes</button></div>
            </form>
        </div></div>
    </div>
    {% endblock %}
    
    {% block scripts %}
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            document.querySelectorAll('.item-checkbox').forEach(cb => {
                cb.addEventListener('change', function() {
                    const itemId = this.dataset.id;
                    const row = this.closest('.list-item-row');
                    if(this.checked) row.classList.add('checked');
                    else row.classList.remove('checked');
                    
                    fetch(`/lists/items/${itemId}/toggle`, { method: 'POST' });
                });
            });

            document.querySelectorAll('.delete-item-btn').forEach(btn => {
                btn.addEventListener('click', function(e) {
                    e.preventDefault();
                    const itemId = this.dataset.id;
                    const row = this.closest('.list-item-row');
                    row.style.opacity = '0';
                    setTimeout(() => row.remove(), 300);
                    
                    fetch(`/lists/items/${itemId}/delete`, { method: 'POST' });
                });
            });

            var el = document.getElementById('sortable-list');
            if(el && !document.getElementById('empty-state')) {
                Sortable.create(el, {
                    handle: '.drag-handle',
                    animation: 150,
                    onEnd: function (evt) {
                        let order = [];
                        document.querySelectorAll('.list-item-row').forEach((row, index) => {
                            order.push({ id: row.dataset.id, sort_order: index });
                        });
                        
                        fetch(`{{ url_for('reorder_list', id=household_list.id) }}`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ order: order })
                        });
                    }
                });
            }
        });
    </script>
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
                {% if supply.store_name %}
                    <p class="text-warning small mb-1"><i class="bi bi-shop"></i> {{ supply.store_name }}</p>
                {% endif %}
                <h2 class="{{ 'text-danger' if supply.quantity <= supply.reorder_threshold else 'text-success' }}">{{ supply.quantity }}</h2>
                <div class="d-grid gap-2 mt-auto">
                    <form action="{{ url_for('use_supply', id=supply.id) }}" method="POST"><button class="btn btn-sm btn-outline-info w-100">Use</button></form>
                    {% if supply.purchase_url %}
                        <a href="{{ supply.purchase_url }}" target="_blank" class="btn btn-sm btn-link text-info text-decoration-none small">Buy Online</a>
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
                        <div class="mb-3"><label class="small text-muted">Context (Location in House)</label><input type="text" name="context" class="form-control bg-dark text-light border-secondary" placeholder="Kitchen, Garage..."></div>
                        <div class="mb-3"><label class="small text-muted">Purchase URL</label><input type="url" name="purchase_url" class="form-control bg-dark text-light border-secondary" placeholder="https://amazon.com/..."></div>
                        <div class="mb-3"><label class="small text-muted">Store/Location (Where to buy)</label><input type="text" name="store_name" class="form-control bg-dark text-light border-secondary" placeholder="e.g. Home Depot, Costco"></div>
                        <hr class="border-secondary">
                        <div class="form-check mb-2">
                            <input class="form-check-input" type="checkbox" name="auto_add_to_shopping" id="autoAdd" checked>
                            <label class="form-check-label small" for="autoAdd">
                                Auto-add to Shopping List when stock is low
                            </label>
                        </div>
                        <div class="form-check mb-2">
                            <input class="form-check-input" type="checkbox" name="add_to_list_now" id="addNow">
                            <label class="form-check-label small text-warning" for="addNow">
                                Add to General Shopping List immediately
                            </label>
                        </div>
                    </div>
                    <div class="modal-footer border-secondary"><button class="btn btn-success w-100">Add Supply</button></div>
                </form>
            </div>
        </div>
    </div>
    {% endblock %}
    """,
    'users.html': """
    {% extends "base.html" %}
    {% block content %}
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2 class="h4 mb-0">Household Members</h2>
        <button class="btn btn-primary btn-sm" data-bs-toggle="modal" data-bs-target="#addUserModal">+ Add Member</button>
    </div>
    <div class="row g-3">
        {% for u in all_users %}
        <div class="col-md-4">
            <div class="card bg-dark border-secondary shadow-sm h-100">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <h5 class="card-title text-light mb-0">{{ u.name }}</h5>
                        <span class="badge {{ 'bg-primary' if u.role == 'admin' else 'bg-secondary' }}">{{ u.role|title }}</span>
                    </div>
                    <p class="text-muted small mb-3">Capacity: {{ u.weekday_capacity_points }} (Wk) / {{ u.weekend_capacity_points }} (Wknd)</p>
                    <button class="btn btn-sm btn-outline-info w-100" data-bs-toggle="modal" data-bs-target="#editUserModal{{ u.id }}">Edit User</button>
                </div>
            </div>
        </div>

        <!-- Edit User Modal -->
        <div class="modal fade" id="editUserModal{{ u.id }}" tabindex="-1">
            <div class="modal-dialog"><div class="modal-content bg-dark text-light border-secondary">
                <form action="{{ url_for('edit_user', id=u.id) }}" method="POST">
                    <div class="modal-header border-secondary"><h5 class="modal-title">Edit {{ u.name }}</h5><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div>
                    <div class="modal-body">
                        <div class="mb-3"><label class="small text-muted">Name</label><input type="text" name="name" class="form-control bg-dark text-light border-secondary" value="{{ u.name }}" required></div>
                        <div class="row g-2 mb-3">
                            <div class="col-6"><label class="small text-muted">Weekday Capacity</label><input type="number" name="weekday" class="form-control bg-dark text-light border-secondary" value="{{ u.weekday_capacity_points }}"></div>
                            <div class="col-6"><label class="small text-muted">Weekend Capacity</label><input type="number" name="weekend" class="form-control bg-dark text-light border-secondary" value="{{ u.weekend_capacity_points }}"></div>
                        </div>
                    </div>
                    <div class="modal-footer border-secondary"><button class="btn btn-success w-100">Save Changes</button></div>
                </form>
            </div></div>
        </div>
        {% endfor %}
    </div>

    <!-- Add User Modal -->
    <div class="modal fade" id="addUserModal" tabindex="-1">
        <div class="modal-dialog"><div class="modal-content bg-dark text-light border-secondary">
            <form action="{{ url_for('add_user') }}" method="POST">
                <div class="modal-header border-secondary"><h5 class="modal-title">Add New Member</h5><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div>
                <div class="modal-body">
                    <div class="mb-3"><label class="small text-muted">Name</label><input type="text" name="name" class="form-control bg-dark text-light border-secondary" placeholder="E.g., Jane" required></div>
                    <div class="row g-2 mb-3">
                        <div class="col-6"><label class="small text-muted">Weekday Capacity</label><input type="number" name="weekday" class="form-control bg-dark text-light border-secondary" value="20"></div>
                        <div class="col-6"><label class="small text-muted">Weekend Capacity</label><input type="number" name="weekend" class="form-control bg-dark text-light border-secondary" value="30"></div>
                    </div>
                </div>
                <div class="modal-footer border-secondary"><button class="btn btn-success w-100">Add Member</button></div>
            </form>
        </div></div>
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
@app.route('/')
def kanban():
    hid = session.get('household_id')
    items = ActionItem.query.filter(ActionItem.household_id==hid, ActionItem.status != 'someday').order_by(ActionItem.created_at.desc()).all()
    return render_template('kanban.html', items=items)

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
    app.run(host='0.0.0.0', port=5000, debug=True)
