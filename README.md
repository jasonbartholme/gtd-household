GTD Household Manager
=====================

A comprehensive, Python-driven household management system built around the "Getting Things Done" (GTD) methodology. This application is designed as a fully functional application using Flask and SQLite, making it easy to deploy locally on a home network.

Key Features
---------------

### The Inbox & Processing

*   **Brain Dump & Bulk Capture:** Quickly capture single thoughts or paste multiple lines at once to get them out of your head and into your inbox.
*   **Clarify Workflow:** A dedicated modal to process inbox items. Transform raw thoughts into actionable tasks, assign them to Projects, give them Contexts (e.g., `@Garage`), or defer them to the `Someday/Maybe` list.
*   **"Save and Next" Button:** A streamlined workflow to rapidly process your entire inbox without leaving the page.

### Workflow & Kanban Board

*   **The Icebox:** A dedicated page for tasks that have been reviewed but are not yet ready for implementation. This keeps the main board clean and focused.
*   **Interactive Board:** A drag-and-drop Kanban interface (powered by SortableJS) with columns for Ready, In Progress, Blocked, and Done.
*   **Recurring Tasks:** Actions can be set to recur automatically. Completing a recurring task automatically calculates the next due date and respawns it in the Icebox.
*   **Contexts & Due Dates:** Assign contexts and due dates to visually track where and when things need to happen.

### Planning & Strategy

*   **Project Management:** Group multi-step outcomes into active Projects. Edit project details, track progress with visual bars, and see the "Next Task" at a glance.
*   **Manual Task Sorting:** Within a project, drag and drop tasks to manually define their priority and execution order.
*   **Someday/Maybe Incubator:** Store ideas you aren't ready to commit to yet, keeping your active board clutter-free. Activate them with a single click when you're ready.
*   **Dynamic Calendar:** A visual monthly calendar grid highlighting days with due actions.
*   **Household Lists:** Create custom, taggable lists (e.g., Groceries, Packing, Menards Run) tied to specific geographical contexts. Features drag-and-drop reordering, quick-add, and soft-deletion.

### Asset & Supply Tracking

*   **Asset Management:** Track valuable household items (vehicles, appliances, electronics) including location, purchase URLs, and check-in/check-out status.
*   **Power Tracking:** Monitor power sources, battery types, and expected battery lifespans.
*   **Cost of Ownership:** Automatically logs and totals all general expenses and maintenance costs associated with an asset.
*   **Maintenance Schedules:** Set up recurring maintenance tasks. Logging completion automatically adds to the asset's expense history and calculates the next due date.
*   **Supply Management:** Keep track of consumables with set reorder thresholds.
*   **Smart Restocking:** When a supply drops below its threshold, the system can automatically add it to a shopping list or generate a new Errand.

### Metrics & Gamification

*   **Complexity Points:** Tasks are assigned complexity points using the Fibonacci sequence (1, 2, 3, 5, 8).
*   **Leaderboard:** Compete with household members! Tracks top daily point earners, all-time high scores, and most recent points awarded.
*   **Weekly Review Hub:** A dedicated screen to guide you through clearing your inbox, reviewing recurring items, and following up on blocked tasks.
*   **Activity Dashboard:** Monitor recent household activity, today's completion count, and manage overall system health.

### Administration & Data Management

*   **Automated Archiving:** A daily scheduled job automatically moves tasks from the "Done" column to the Archive, keeping the board focused on current work.
*   **Archive Page:** A paginated and searchable view of all completed tasks and projects.
*   **Multi-User Environment:** Support for multiple household members with configurable capacity limits.
*   **Data Portability:** 1-click JSON export of the entire database for seamless backups. Restore from a JSON file.
*   **Admin Purge:** Admins can execute a hard purge to permanently delete stale, soft-deleted data.
*   **Timezone Aware:** Uses `zoneinfo` to ensure all timestamps are correctly aligned.

Setup & Installation
-----------------------

This application is designed for easy local setup.

1.  **Prerequisites:** Make sure you have Python 3.9+ installed.
2.  `pip install -r requirements.txt`
3.  python app.py
4.  **Access:** Open your browser and navigate to http://localhost:5000. The SQLite database (gtd.db) will be created automatically on the first run, seeded with sample demo data.

Tech Stack
-------------

*   **Backend:** Python, Flask, Flask-SQLAlchemy, SQLite
*   **Frontend:** Jinja2 Templates, Bootstrap 5.3 (Dark Theme), Vanilla JavaScript
*   **Scheduling:** Flask-APScheduler
*   **Libraries:** SortableJS (for drag-and-drop functionality)
