import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import requests

import streamlit as st

from api_client import (
	add_task,
	delete_task,
	get_tasks,
	get_tasks_today,
	update_task,
	get_base_url,
)


def format_datetime_for_display(dt_str: str) -> str:
	try:
		return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
	except Exception:
		return dt_str


def parse_datetime_to_iso(selected_dt: datetime) -> str:
	# Ensure ISO 8601 string (assume local time if naive)
	if selected_dt.tzinfo is None:
		return selected_dt.isoformat()
	return selected_dt.astimezone().isoformat()


def task_status_color(status: str) -> str:
	return "✅ Done" if status.lower() == "done" else "🕒 Pending"


def safe_rerun() -> None:
	if hasattr(st, "rerun"):
		st.rerun()
	elif hasattr(st, "experimental_rerun"):
		st.experimental_rerun()


def datetime_input_compat(label: str, value: Optional[datetime]) -> datetime:
	"""Fallback for older Streamlit versions without st.datetime_input."""
	if hasattr(st, "datetime_input"):
		return st.datetime_input(label, value=value)
	# Fallback to separate date & time inputs
	default_dt = value or (datetime.now() + timedelta(hours=1))
	selected_date = st.date_input(f"{label} (date)", value=default_dt.date())
	selected_time = st.time_input(f"{label} (time)", value=default_dt.time())
	return datetime.combine(selected_date, selected_time)


def render_sidebar() -> Tuple[str, str]:
	st.sidebar.title("Reminder Agent")
	page = st.sidebar.radio(
		"Navigation",
		options=["Add Task", "View Tasks", "Today’s Schedule", "Reminders"],
	)
	default_api = os.getenv("API_BASE_URL", "http://localhost:9000")
	api_base = st.sidebar.text_input("API Base URL", value=default_api, help="FastAPI base, e.g., http://localhost:8000")
	colA, colB = st.sidebar.columns([1, 1])
	with colA:
		check = st.button("Check API", use_container_width=True)
	with colB:
		st.sidebar.write("")

	if check:
		from api_client import get_tasks
		_, err = get_tasks(api_base)
		if err:
			st.sidebar.error(f"API unreachable: {err}")
		else:
			st.sidebar.success("API OK")
	st.sidebar.caption("Use the sidebar to navigate and configure the API endpoint.")
	return page, api_base


def page_add_task(api_base_url: str) -> None:
	st.header("Add / Update / Delete Task")

	with st.expander("Existing Tasks", expanded=False):
		all_tasks, err = get_tasks(api_base_url)
		if err:
			st.warning(f"Failed to load tasks: {err}")
		else:
			if not all_tasks:
				st.info("No tasks yet.")
			else:
				for t in all_tasks:
					st.write(f"- {t.get('name','(no name)')} — due {format_datetime_for_display(t.get('due_datetime',''))} — {task_status_color(t.get('status','Pending'))}")

	mode = st.radio("Action", ["Add", "Update", "Delete"], horizontal=True)

	# Prepare state for update/delete
	selected_task: Optional[Dict[str, Any]] = None
	all_tasks, load_err = get_tasks(api_base_url)
	if load_err:
		st.warning(f"Failed to load tasks: {load_err}")
		all_tasks = []

	if mode in ("Update", "Delete"):
		choices = {f"{t.get('name','(no name)')} (id: {t.get('id')})": t for t in all_tasks}
		label = st.selectbox("Select Task", list(choices.keys())) if choices else None
		selected_task = choices.get(label) if label else None

	default_name = selected_task.get("name") if selected_task else ""
	default_desc = selected_task.get("description") if selected_task else ""
	default_due = None
	if selected_task and selected_task.get("due_datetime"):
		try:
			default_due = datetime.fromisoformat(selected_task["due_datetime"].replace("Z", "+00:00"))
		except Exception:
			default_due = None

	name = st.text_input("Task name", value=default_name)
	description = st.text_area("Description (optional)", value=default_desc)
	due_dt = datetime_input_compat("Due date & time", value=default_due or (datetime.now() + timedelta(hours=1)))

	col1, col2, col3 = st.columns(3)
	with col1:
		if st.button("Add Task", type="primary", disabled=(mode != "Add")):
			if not name.strip():
				st.error("Task name is required.")
			else:
				payload = {"name": name.strip(), "description": description.strip(), "due_datetime": parse_datetime_to_iso(due_dt)}
				created, err = add_task(api_base_url, payload)
				if err:
					st.error(f"Failed to add task: {err}")
				else:
					st.success("Task added successfully.")
					safe_rerun()
	with col2:
		if st.button("Update Task", disabled=(mode != "Update" or not selected_task)):
			if not selected_task:
				st.warning("Select a task to update.")
			else:
				payload = {
					"name": name.strip() or selected_task.get("name",""),
					"description": description.strip(),
					"due_datetime": parse_datetime_to_iso(due_dt),
				}
				updated, err = update_task(api_base_url, selected_task.get("id"), payload)
				if err:
					st.error(f"Failed to update task: {err}")
				else:
					st.success("Task updated successfully.")
					safe_rerun()
	with col3:
		if st.button("Delete Task", disabled=(mode != "Delete" or not selected_task)):
			if not selected_task:
				st.warning("Select a task to delete.")
			else:
				ok, err = delete_task(api_base_url, selected_task.get("id"))
				if err:
					st.error(f"Failed to delete task: {err}")
				else:
					st.success("Task deleted successfully.")
					safe_rerun()


def page_view_tasks(api_base_url: str) -> None:
	st.header("All Tasks")
	tasks, err = get_tasks(api_base_url)
	if err:
		st.error(f"Failed to fetch tasks: {err}")
		return
	if not tasks:
		st.info("No tasks found.")
		return

	# Sort by due date
	try:
		tasks = sorted(tasks, key=lambda t: t.get("due_datetime") or "")
	except Exception:
		pass

	for t in tasks:
		with st.container(border=True):
			left, mid, right = st.columns([4, 3, 2])
			with left:
				st.subheader(t.get("name", "(no name)"))
				if t.get("description"):
					st.write(t["description"])
			with mid:
				st.caption("Due")
				st.write(format_datetime_for_display(t.get("due_datetime", "")))
			with right:
				status_text = task_status_color(t.get("status", "Pending"))
				st.write(status_text)
				if t.get("status", "Pending").lower() != "done":
					if st.button("Mark Done", key=f"done-{t.get('id')}"):
						payload = {"status": "Done"}
						_, uerr = update_task(api_base_url, t.get("id"), payload)
						if uerr:
							st.error(f"Failed to mark done: {uerr}")
						else:
							st.success("Marked as done.")
							safe_rerun()


def page_today_schedule(api_base_url: str) -> None:
	st.header("Today’s Schedule")
	tasks, err = get_tasks_today(api_base_url)
	if err:
		st.error(f"Failed to fetch today’s tasks: {err}")
		return

	if not tasks:
		st.info("You have no tasks due today. 🎉")
		return

	now = datetime.now()
	for t in tasks:
		is_due_soon = False
		try:
			if t.get("due_datetime"):
				due = datetime.fromisoformat(t["due_datetime"].replace("Z", "+00:00"))
				is_due_soon = 0 <= (due - now).total_seconds() <= 3600
		except Exception:
			is_due_soon = False

		with st.container(border=True):
			if is_due_soon and t.get("status", "Pending").lower() != "done":
				st.markdown("**⏰ Due within 1 hour!**")
			st.subheader(t.get("name", "(no name)"))
			if t.get("description"):
				st.write(t["description"])
			st.caption(f"Due: {format_datetime_for_display(t.get('due_datetime',''))}")
			st.write(task_status_color(t.get("status", "Pending")))


def page_reminders(api_base_url: str) -> None:
    st.header("🔔 Due Reminders")

    try:
        # Call your FastAPI reminders endpoint
        resp = requests.get(f"{api_base_url.rstrip('/')}/reminders", timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        st.error(f"Failed to fetch reminders: {e}")
        return

    due_reminders = data.get("due_reminders", [])

    if not due_reminders:
        st.info("✅ No reminders due right now.")
        return

    for r in due_reminders:
        with st.container(border=True):
            st.subheader(r.get("task", "Unnamed Reminder"))
            st.caption(f"Scheduled at: {r.get('time')}")
            if r.get("triggered"):
                st.success("Reminder already triggered")
            else:
                st.warning("⏰ Upcoming reminder")


def main() -> None:
	st.set_page_config(page_title="Reminder Agent", page_icon="⏰", layout="centered")
	page, api_base = render_sidebar()
	st.session_state.setdefault("api_base_url", api_base or get_base_url())
	if api_base and api_base != st.session_state["api_base_url"]:
		st.session_state["api_base_url"] = api_base

	if page == "Add Task":
		page_add_task(st.session_state["api_base_url"])
	elif page == "View Tasks":
		page_view_tasks(st.session_state["api_base_url"])
	elif page == "Today’s Schedule":
		page_today_schedule(st.session_state["api_base_url"])
	elif page == "Reminders":
		page_reminders(st.session_state["api_base_url"])

if __name__ == "__main__":
	main()


