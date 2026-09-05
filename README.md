GTD Household Manager
=====================

A comprehensive, Python-driven household management system built around the "Getting Things Done" (GTD) methodology. This application is designed as a fully functional application using Flask and SQLite, making it easy to deploy locally on a home network.

Key Features
------------

### Inbox & Assigned Work

*   **Capture:** Use the global **New Task** action to get tasks and ideas out of your head quickly.
*   **My Tasks:** The Inbox route presents active tasks assigned to the current household member, including collaborative tasks.
*   **Assignment Groups:** Tasks assigned by another household member appear separately above tasks you own, making delegated work easy to spot.
*   **Relative Due Dates:** Assigned tasks use calendar-aware labels such as `Due today`, `Due tomorrow`, and `Due in 3 days`.

<img width="1412" height="839" alt="board-view" src="https://github.com/user-attachments/assets/a911a7db-791e-485d-92d6-47be0ddc74ce" />

### Workflow & Kanban Board

*   **The Icebox:** A dedicated page for tasks that have been reviewed but are not yet ready for implementation. This keeps the main board clean and focused.
*   **Interactive Board:** A drag-and-drop Kanban interface (powered by SortableJS) with columns for Ready, In Progress, Blocked, and Done.
*   **Compact View Toggle:** Switch between a full and compact view of tasks on the Kanban board to manage visual clutter.
*   **Task Details:** Tasks now include fields for `Time Estimate` (in minutes) and `Energy Level` (Low, Medium, High) to aid in task selection.
*   **Collaborator Assignment:** Assign multiple users to a task. Shared Board cards identify the person who assigned the task to the current viewer.
*   **Recurring Tasks:** Actions can be set to recur automatically. Completing a recurring task automatically calculates the next due date and respawns it in the Icebox.
*   **Contexts & Due Dates:** Assign contexts and due dates to visually track where and when things need to happen.

<img width="1419" height="856" alt="active-projecs-view" src="https://github.com/user-attachments/assets/ec85d8cf-4d78-4c55-a7ce-4e7898bd4a46" />

### Planning & Strategy

*   **Project Management:** Group multi-step outcomes into active Projects. Edit project details, track progress with visual bars, and see the "Next Task" at a glance.
*   **Project Completion Percentage:** See the percentage of tasks completed for each project on both the main Projects page and the Project Detail page, including archived tasks in the calculation.
*   **Project-Asset Association:** Link projects to specific assets to track work history and costs related to an item.
*   **Manual Task Sorting:** Within a project, drag and drop tasks to manually define their priority and execution order.
*   **Project Images:** Upload, caption, edit, and delete project images with generated thumbnails and storage statistics.
*   **Someday/Maybe Incubator:** Store ideas you aren't ready to commit to yet, keeping your active board clutter-free. Activate them with a single click when you're ready.
*   **Dynamic Calendar:** A visual monthly calendar grid highlighting days with due actions, now offering both grid and list views.
*   **Household Lists:** Create custom, searchable, taggable lists (e.g., Groceries, Packing, Menards Run) tied to specific geographical contexts. Features drag-and-drop reordering, quick-add, filtering, sorting, and soft-deletion.
*   **General Shopping List:** Capture unassigned shopping items quickly, then check them off, remove them, or reorder them independently of a named list.

<img width="1430" height="849" alt="project-detail-view" src="https://github.com/user-attachments/assets/8262279b-1b5f-41a4-922b-9f0a4f732619" />

### Asset & Supply Tracking

*   **Asset Management:** Track valuable household items (vehicles, appliances, electronics) including location, purchase URLs, and check-in/check-out status. Asset pages now display related active and completed projects.
*   **Power Tracking:** Monitor power sources, battery types, and expected battery lifespans.
*   **Cost of Ownership:** Automatically logs and totals all general expenses and maintenance costs associated with an asset.
*   **Maintenance Schedules:** Set up recurring maintenance tasks. Logging completion automatically adds to the asset's expense history and calculates the next due date.
*   **Supply Management:** Keep track of consumables with reorder thresholds in a context-grouped, horizontal store-friendly view.
*   **Supply Images:** Upload an optional square item image to make supplies easier to recognize while reordering. Supplies without an image use an item-icon fallback.
*   **Smart Restocking:** When a supply drops below its threshold, the system can automatically add it to a shopping list or generate a new Errand.
*   **Expense Management:** Track project-specific expenses with fields for amount, description, notes, source, URL, and date. Expenses are linked to projects and displayed on project detail pages. A dedicated "Expenses" page allows for editing, soft-deleting, and paginating expense records.
*   **Expense Reporting:** Review monthly expense totals in a chart and filter recent project expenses by date range.

<img width="1417" height="843" alt="archive-view" src="https://github.com/user-attachments/assets/881dc812-92fc-4355-ba33-7135e8e8ffd3" />

### Metrics & Collaboration

*   **Complexity Points:** Tasks are assigned complexity points using the Fibonacci sequence (1, 2, 3, 5, 8).
*   **Leaderboard:** Compete with household members! The enhanced leaderboard tracks today's top point earners, today's top task finishers, and the top 20 daily point totals and task counts of all time.
*   **Today's Done Page:** A dedicated page to view all tasks completed today, along with total tasks and points earned for the day.
*   **Weekly Review Hub:** A dedicated screen to guide you through clearing your inbox, reviewing recurring items, and following up on blocked tasks.
*   **Activity Dashboard:** Monitor recent household activity and today's completion count.
*   **Multi-User Environment:** Support for multiple household members with configurable weekday and weekend capacity limits, plus user switching from the navigation.

### Administration & Data Management

*   **Automated Archiving:** A daily scheduled job automatically moves tasks from the "Done" column to the Archive, keeping the board focused on current work. Administrators can also trigger the job manually.
*   **Archive Page:** A paginated and searchable view of all completed tasks and projects.
*   **Task Defaults:** Configure household defaults for task context, time estimate, due-date offset, and energy level to standardize incoming work.
*   **New-User Guidance:** GTD-oriented page descriptions can be shown or hidden globally from the admin panel.
*   **Settings Page:** Available at `/admin` (and `/settings`) for database health, activity, active lists, image counts, upload storage, task defaults, and UI preferences.
*   **Data Portability:** 1-click JSON export of the entire database for seamless backups. Restore from a JSON file.
*   **Automatic Backups:** A daily scheduler creates a JSON backup when activity has changed since the previous backup.
*   **Admin Purge:** Admins can execute a hard purge to permanently delete stale, soft-deleted lists and list items.
*   **Timezone Aware:** Uses `zoneinfo` with America/Chicago timestamps for application activity and scheduling.

Setup & Installation
-----------------------

This application is designed for easy local setup.

1.  **Prerequisites:** Ensure Python 3.12 is installed.
2.  **Create a virtual environment:** Run `python3.12 -m venv venv` and activate it with `source venv/bin/activate`.
3.  **Install Dependencies:** Run `pip install -r requirements.txt` in your project directory.
4.  **Run the Application:** Execute `python app.py` from your project directory.
5.  **Access:** Open your web browser and navigate to `http://localhost:5000`. The SQLite database (`app.db`) will be created automatically on the first run, seeded with sample demo data.
6.  **Backups and uploads:** JSON backups are written to `backups/`; project, asset, and supply images are stored under `static/uploads/`.

Tech Stack
-------------

*   **Backend:** Python, Flask, Flask-SQLAlchemy, SQLite
*   **Frontend:** Jinja2 Templates, Bootstrap 5.3 (Dark Theme), Vanilla JavaScript
*   **Scheduling:** Flask-APScheduler
*   **Libraries:** SortableJS (drag-and-drop), Chart.js (expense charts), Pillow (image thumbnails), and APScheduler (scheduled jobs)
