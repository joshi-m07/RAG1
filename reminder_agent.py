from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

app = FastAPI()
scheduler = BackgroundScheduler()
scheduler.start()

reminders = []  # Store reminders temporarily (later connect to DB)


# Endpoint to add a reminder
@app.post("/add_reminder/")
def add_reminder(task: str, minutes_from_now: int):
    reminder_time = datetime.now() + timedelta(minutes=minutes_from_now)
    reminders.append({"task": task, "time": reminder_time, "triggered": False})

    # Schedule a job
    scheduler.add_job(
        func=send_reminder,
        trigger="date",
        run_date=reminder_time,
        args=[task],
    )

    return {"message": f"Reminder set for '{task}' at {reminder_time}"}


# Endpoint to view all reminders
@app.get("/reminders/")
def get_reminders():
    return {"reminders": reminders}


# ✅ New endpoint: fetch due reminders (for Streamlit)
@app.get("/get_due_reminders/")
def get_due_reminders():
    now = datetime.now()
    due = []
    for r in reminders:
        if r["time"] <= now and not r["triggered"]:
            r["triggered"] = True  # mark as shown
            due.append(r)
    return {"due_reminders": due}


# Function to simulate sending reminder
def send_reminder(task):
    print(f"🔔 Reminder: {task} (at {datetime.now()})")
