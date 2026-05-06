# GTD Household Manager 🏡
A comprehensive, self-hosted household management web application inspired by the Getting Things Done (GTD) methodology. Built with Python, Flask, and SQLite, this application helps you brain-dump tasks, organize chores, track assets, manage consumable supplies, and monitor the total cost of ownership for your household items.
## 🚀 Key Features
* **Brain Dump Inbox:** Quick-capture UI for logging thoughts. Supports bulk pasting (e.g., pasting a list of 30 items for the "Garage" context at once).
* **Kanban Workflow:** Visualize your work with *Ready, Doing, Blocked,* and *Done* columns. Supports drag-and-drop prioritization.
* **Calendar View:** A month-at-a-glance visualization for scheduled tasks, due dates, and recurring chores.
* **Recurrence Engine:** Tasks can be set to recur (Days/Weeks/Months). When marked "Done," the next instance automatically respawns on the board, carrying over linked assets and supplies.
* **Asset & Battery Tracking:** Register vehicles, electronics, and tools. Track power sources, battery lifespans, and check-in/check-out status.
* **Inventory & Supplies:** Track quantities of consumables (e.g., oil filters, cleaning supplies). Automatically generates an "Errand" on your board when stock dips below the reorder threshold.
* **Maintenance Schedules & Cost Dashboards:** Schedule regular maintenance (e.g., 180-day oil changes). Log completions to auto-calculate the next due date and feed into the Asset's "Total Cost of Ownership" financial ledger.
* **Weekly Review:** A dedicated dashboard to audit your unprocessed inbox, blocked items, and active recurring chores.
* **Data Portability:** 100% local operation with one-click JSON database export and import for seamless backups and resets.
## 🛠️ Installation
**Prerequisites:** Python 3.8+
1. **Clone the repository**

    git clone https://github.com/jasonbartholme/gtd-household.git
    cd gtd-household

2. **Create a virtual environment (Recommended)**

    python -m venv venv
**On macOS/Linux:**
    source venv/bin/activate
**On Windows:**
    venv\Scripts\activate

4. **Install dependencies**

    pip install Flask Flask-SQLAlchemy

5. **Run the application**

    python app.py

Note: On the first run, the application will automatically create the gtd.db SQLite database and seed it with default household data.*

5. **Open in your browser**
Navigate to http://localhost:5000
## 📖 How to Use (The Workflow)
This app is designed around a continuous flow of productivity:
1. **Capture (Inbox):** Whenever a thought crosses your mind ("Replace furnace filter", "Fix leaky faucet"), drop it in the **Inbox**. Use the Bulk dump tab after a brainstorming session.
2. **Clarify (Process):** Go to the Inbox and click "Process". Decide if the item is a Task, Chore, or Errand. Assign a Context (e.g., @Kitchen), a "Chorenado" complexity score (Fibonacci), and establish if it needs to recur.
3. **Organize (Assets & Supplies):** Link your Tasks to specific physical Assets or Required Supplies. (e.g., Link an "Oil Change" task to the "VW Wagen" asset and the "5W-30 Oil" supply).
4. **Reflect (Review):** Use the **Review** tab weekly to ensure your Inbox is at zero, audit tasks you are "Waiting On", and check your active recurring schedules.
5. **Engage (Kanban & Calendar):** Work off the Kanban board. Drag items into "Doing", and finally to "Done" to log the activity and trigger any auto-respawns.
## 🗺️ Future Roadmap
While the MVP is fully functional, here are the logical next steps for development based on the core architecture goals:
- [ ] **External Sync:** Two-way integration with Google Calendar / CalDAV for scheduled time-blocking.
- [ ] **Geolocation Errands:** Attach Lat/Long coordinates to "Errands" to enable proximity-based sorting (e.g., "Show me hardware store errands when I am near Home Depot").
- [ ] **Multiplayer Enhancements:** Expand the capacity tracking system so household members can "spend" their Weekday/Weekend capacity points on tasks.
- [ ] **QR Code Scanning:** Generate printable QR codes for Assets to enable fast check-out/check-in via smartphone camera.
- [ ] **Push Notifications:** PWA (Progressive Web App) support to deliver browser push notifications for overdue maintenance and low-stock supplies.
## 🤝 Contributing
Pull requests are welcome! If you're planning a major change or database schema update, please open an issue first to discuss what you would like to change.
Remember to clear or migrate your gtd.db when making changes to SQLAlchemy models.
## 📄 License
[MIT](https://choosealicense.com/licenses/mit/)
