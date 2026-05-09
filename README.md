GTD Household Manager
=====================

A comprehensive, Python-driven household management system built around the "Getting Things Done" (GTD) methodology. This application is designed as a fully functional, single-file MVP using Flask and SQLite, making it incredibly easy to deploy locally on a home network.

🌟 Key Features
---------------

### 📥 The Inbox & Processing

*   **Brain Dump:** Quickly capture raw thoughts, ideas, and open loops to get them out of your head.
    
*   **Bulk Capture:** Paste multiple items at once to quickly populate your inbox.
    
*   **Clarify Workflow:** Transform raw thoughts into actionable Next Actions, assign them to Projects, give them Contexts (e.g., @Garage), or defer them to the Someday/Maybe list.
    

### 📋 Workflow & Kanban Board

*   **Interactive Board:** Drag-and-drop Kanban interface powered by SortableJS with columns for Ready, Doing, Blocked (Waiting On), and Done.
    
*   **Smart Filtering:** Quickly toggle the "Ready" column to view All items, Recurring chores, Project-specific actions, or Errands.
    
*   **Action Types:** Categorize items as Tasks, Chores, or Errands.
    
*   **Recurring Tasks:** Actions can be set to recur automatically (e.g., every 2 weeks). Completing a recurring task automatically calculates the next due date and respawns it on the board.
    
*   **Contexts & Due Dates:** Visually track where things need to happen and when they are due.
    

### 🗺️ Planning & Strategy

*   **Project Management:** Group multi-step outcomes into active Projects. Track progress via visual progress bars calculated from completed next actions.
    
*   **Someday / Maybe Incubator:** Store ideas you aren't ready to commit to yet, keeping your active board clutter-free. Activate them with a single click.
    
*   **Dynamic Calendar:** A visual monthly calendar grid highlighting days with due actions.
    
*   **Household Lists:** Create custom, taggable lists (e.g., Groceries, Packing, Menards Run) tied to specific geographical contexts. Features drag-and-drop reordering, quick-add, and soft-deletion.
    

### 🛠️ Asset & Supply Tracking

*   **Asset Management:** Track valuable household items (vehicles, appliances, electronics) including location, purchase URLs, and check-in/check-out status.
    
*   **Power Tracking:** Monitor power sources, battery types, and expected battery lifespans for relevant assets.
    
*   **Cost of Ownership Dashboard:** Automatically logs and totals all general expenses and maintenance costs associated with an asset.
    
*   **Maintenance Schedules:** Setup recurring maintenance tasks (e.g., "Synthetic Oil Change every 180 days"). Logging completion automatically adds to the asset's expense history and calculates the next due date.
    
*   **Supply Management:** Keep track of consumables with set reorder thresholds.
    
*   **Smart Restocking:** When a supply drops below its threshold, the system can automatically add it to your General Shopping List or generate a new Errand to restock it. Link supplies directly to the assets that use them.
    

### 🏆 Metrics & Gamification

*   **The "Chorenado" System:** Tasks are assigned complexity points using the Fibonacci sequence (1, 2, 3, 5, 8, 13).
    
*   **Leaderboard:** Compete with household members! Tracks the top daily point earners, all-time high scores, and most recent points awarded.
    
*   **Weekly Review Hub:** A dedicated screen to guide you through clearing your inbox, reviewing recurring items, and following up on blocked tasks.
    
*   **Activity Dashboard:** Monitor recent household activity, today's completion count, and manage overall system health.
    

### ⚙️ Administration & Data Management

*   **Multi-User Environment:** Support for multiple household members with configurable weekday and weekend capacity limits.
    
*   **Data Portability:** 1-click JSON export of the entire database for seamless backups. Restore functionality to import your JSON data securely.
    
*   **Admin Purge:** Soft-deleted list items and lists are kept for 30 days. Admins can execute a hard purge to permanently delete stale data and keep the database optimized.
    
*   **Timezone Aware:** Uses the zoneinfo library to ensure all database entries and Chorenado points correctly align with Central Time (US/Chicago).
    

🚀 Setup & Installation
-----------------------

This MVP is self-contained within a single Python file, along with inline HTML/Jinja2 templates, making setup virtually instant.

1.  **Prerequisites:** Make sure you have Python 3.9+ installed.
    
2.  pip install flask flask-sqlalchemy tzdata
    
3.  python app.py
    
4.  **Access:** Open your browser and navigate to http://localhost:5000. The SQLite database (gtd.db) will be created automatically on the first run, seeded with sample demo data.
    

💻 Tech Stack
-------------

*   **Backend:** Python, Flask, Flask-SQLAlchemy, SQLite
    
*   **Frontend:** Embedded Jinja2 Templates, Bootstrap 5.3.2 (Dark Theme), Vanilla JavaScript
    
*   **Libraries:** SortableJS (for drag-and-drop functionality)
