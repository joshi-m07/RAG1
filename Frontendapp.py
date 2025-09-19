import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
import requests

# -----------------------------
# UTILS
# -----------------------------
def format_datetime_for_display(dt_str: str) -> str:
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return dt_str

def parse_datetime_to_iso(selected_dt: datetime) -> str:
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
    if hasattr(st, "datetime_input"):
        return st.datetime_input(label, value=value)
    default_dt = value or (datetime.now() + timedelta(hours=1))
    selected_date = st.date_input(f"{label} (date)", value=default_dt.date())
    selected_time = st.time_input(f"{label} (time)", value=default_dt.time())
    return datetime.combine(selected_date, selected_time)

# -----------------------------
# API CALLS (via MCP)
# -----------------------------
def call_mcp(api_base: str, action: str, payload: dict = {}) -> Tuple[Optional[Any], Optional[str]]:
    url = f"{api_base.rstrip('/')}/mcp"
    body = {"agent": "scheduler", "action": action, "payload": payload}
    try:
        resp = requests.post(url, json=body, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success", False):
            return None, data.get("error", "Unknown error")
        return data.get("data"), None
    except requests.RequestException as e:
        return None, str(e)

def add_task(api_base: str, payload: dict) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    return call_mcp(api_base, "add_task", payload)

def get_tasks(api_base: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    return call_mcp(api_base, "get_tasks") or ([], None)

def get_tasks_today(api_base: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    return call_mcp(api_base, "get_tasks_today") or ([], None)

def update_task(api_base: str, task_id: int, payload: dict) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    payload["id"] = task_id
    return call_mcp(api_base, "update_task", payload)

def delete_task(api_base: str, task_id: int) -> Tuple[bool, Optional[str]]:
    _, err = call_mcp(api_base, "delete_task", {"id": task_id})
    return True if err is None else False, err

# -----------------------------
# FRONTEND PAGES
# -----------------------------
def render_sidebar() -> Tuple[str, str]:
    st.sidebar.title("Reminder Agent")
    page = st.sidebar.radio("Navigation", ["Add Task", "View Tasks", "Today’s Schedule"])
    default_api = os.getenv("API_BASE_URL", "http://localhost:8000")
    api_base = st.sidebar.text_input("API Base URL", value=default_api)
    colA, _ = st.sidebar.columns([1,1])
    with colA:
        check = st.button("Check API")
    if check:
        _, err = get_tasks(api_base)
        if err:
            st.sidebar.error(f"API unreachable: {err}")
        else:
            st.sidebar.success("API OK")
    return page, api_base

def page_add_task(api_base: str) -> None:
    st.header("Add / Update / Delete Task")
    all_tasks, _ = get_tasks(api_base)

    mode = st.radio("Action", ["Add", "Update", "Delete"], horizontal=True)
    selected_task: Optional[Dict[str, Any]] = None

    if mode in ("Update", "Delete") and all_tasks:
        choices = {f"{t.get('name')} (id:{t.get('id')})": t for t in all_tasks}
        label = st.selectbox("Select Task", list(choices.keys()))
        selected_task = choices.get(label)

    default_name = selected_task.get("name") if selected_task else ""
    default_desc = selected_task.get("description") if selected_task else ""
    default_due = None
    if selected_task and selected_task.get("due_datetime"):
        try:
            default_due = datetime.fromisoformat(selected_task["due_datetime"].replace("Z", "+00:00"))
        except Exception:
            default_due = None

    name = st.text_input("Task name", value=default_name)
    description = st.text_area("Description", value=default_desc)
    due_dt = datetime_input_compat("Due date & time", value=default_due or (datetime.now() + timedelta(hours=1)))

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Add Task", disabled=(mode != "Add")):
            if not name.strip():
                st.error("Task name required")
            else:
                payload = {"name": name.strip(), "description": description.strip(), "due_datetime": parse_datetime_to_iso(due_dt)}
                _, err = add_task(api_base, payload)
                if err: st.error(err)
                else: st.success("Task added"); safe_rerun()
    with col2:
        if st.button("Update Task", disabled=(mode != "Update" or not selected_task)):
            payload = {"name": name.strip(), "description": description.strip(), "due_datetime": parse_datetime_to_iso(due_dt)}
            _, err = update_task(api_base, selected_task["id"], payload)
            if err: st.error(err)
            else: st.success("Task updated"); safe_rerun()
    with col3:
        if st.button("Delete Task", disabled=(mode != "Delete" or not selected_task)):
            _, err = delete_task(api_base, selected_task["id"])
            if err: st.error(err)
            else: st.success("Task deleted"); safe_rerun()

def page_view_tasks(api_base: str) -> None:
    st.header("All Tasks")
    tasks, _ = get_tasks(api_base)
    for t in tasks:
        left, mid, right = st.columns([4,3,2])
        with left:
            st.subheader(t.get("name"))
            if t.get("description"): st.write(t.get("description"))
        with mid:
            st.caption("Due"); st.write(format_datetime_for_display(t.get("due_datetime","")))
        with right:
            st.write(task_status_color(t.get("status","Pending")))
            if t.get("status","Pending").lower() != "done":
                if st.button("Mark Done", key=f"done-{t.get('id')}"):
                    _, err = update_task(api_base, t.get("id"), {"status":"Done"})
                    if err: st.error(err)
                    else: st.success("Marked done"); safe_rerun()

def page_today_schedule(api_base: str) -> None:
    st.header("Today’s Schedule")
    tasks, _ = get_tasks_today(api_base)
    now = datetime.now()
    for t in tasks:
        due_soon = False
        if t.get("due_datetime"):
            try: due = datetime.fromisoformat(t["due_datetime"].replace("Z","+00:00"))
            except: due = None
            if due: due_soon = 0 <= (due - now).total_seconds() <= 3600
        if due_soon and t.get("status","Pending").lower() != "done":
            st.markdown("**⏰ Due within 1 hour!**")
        st.subheader(t.get("name"))
        if t.get("description"): st.write(t.get("description"))
        st.caption(f"Due: {format_datetime_for_display(t.get('due_datetime',''))}")
        st.write(task_status_color(t.get("status","Pending")))

# -----------------------------
# MAIN
# -----------------------------
def main():
    st.set_page_config(page_title="Reminder Agent", page_icon="⏰", layout="centered")
    page, api_base = render_sidebar()
    if page == "Add Task": page_add_task(api_base)
    elif page == "View Tasks": page_view_tasks(api_base)
    else: page_today_schedule(api_base)

if __name__ == "__main__":
    main()
