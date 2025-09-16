# backend.py
"""
FastAPI backend for Scheduling & Conflict Resolver Agent
- SQLite storage (events table)
- Endpoints: add, list, check_conflicts, suggestions, apply_suggestion, clear_db
- Rule-based rescheduling algorithm
- Optional LLM natural-language explanation if OPENAI_API_KEY is set (LangChain/OpenAI)
"""

import os
import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException

# Optional LLM imports (agent-like natural language output)
USE_LLM = bool(os.getenv("OPENAI_API_KEY"))
if USE_LLM:
    try:
        from langchain_openai import ChatOpenAI
        from langchain.prompts import ChatPromptTemplate
    except Exception:
        USE_LLM = False

DB_PATH = "events.db"
DATEFMT = "%Y-%m-%dT%H:%M"

app = FastAPI(title="Scheduling & Conflict Resolver Agent")

# ---------- DB helpers ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            start_iso TEXT NOT NULL,
            end_iso TEXT NOT NULL,
            place TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_event_db(title: str, start_iso: str, end_iso: str, place: Optional[str] = None):
    s = datetime.fromisoformat(start_iso)
    e = datetime.fromisoformat(end_iso)
    if e <= s:
        raise ValueError("end must be after start")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO events (title, start_iso, end_iso, place) VALUES (?, ?, ?, ?)",
        (title, start_iso, end_iso, place or ""),
    )
    conn.commit()
    ev_id = c.lastrowid
    conn.close()
    return ev_id

def list_events_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, start_iso, end_iso, place FROM events ORDER BY start_iso")
    rows = c.fetchall()
    conn.close()
    events = []
    for r in rows:
        events.append({
            "id": r[0],
            "title": r[1],
            "start": r[2],
            "end": r[3],
            "place": r[4]
        })
    return events

def update_event_time_db(event_id: int, new_start_iso: str, new_end_iso: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE events SET start_iso = ?, end_iso = ? WHERE id = ?", (new_start_iso, new_end_iso, event_id))
    conn.commit()
    conn.close()

def clear_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()

# ---------- Models ----------
class EventIn(BaseModel):
    title: str
    start_iso: str
    end_iso: str
    place: Optional[str] = None

class EventOut(BaseModel):
    id: int
    title: str
    start_iso: str
    end_iso: str
    place: Optional[str] = None

class ConflictPair(BaseModel):
    a: EventOut
    b: EventOut

class Suggestion(BaseModel):
    move_event: EventOut
    new_start_iso: str
    new_end_iso: str
    reason: str
    llm_explanation: Optional[str] = None

# ---------- Scheduling logic ----------
def check_conflicts():
    evs = []
    raw = list_events_db()
    for r in raw:
        evs.append({
            "id": r["id"],
            "title": r["title"],
            "start": datetime.fromisoformat(r["start"]),
            "end": datetime.fromisoformat(r["end"]),
            "place": r["place"]
        })
    conflicts = []
    n = len(evs)
    for i in range(n):
        for j in range(i+1, n):
            a = evs[i]; b = evs[j]
            if a["start"] < b["end"] and b["start"] < a["end"]:
                conflicts.append((a,b))
    return conflicts

def round_up_to_5min(dt: datetime):
    minute = (dt.minute + 4) // 5 * 5
    return dt.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=minute)

def find_free_slot(all_events, duration_minutes: int, after_time: Optional[datetime]=None, search_days=7):
    if after_time is None:
        after_time = datetime.now()
    probe = round_up_to_5min(after_time)
    duration = timedelta(minutes=duration_minutes)
    for day_offset in range(search_days):
        day = (probe + timedelta(days=day_offset)).date()
        busy = []
        for ev in all_events:
            if ev["start"].date() == day:
                busy.append((ev["start"], ev["end"]))
        busy.sort()
        day_start = datetime.combine(day, datetime.min.time()) + timedelta(hours=8)
        day_end = datetime.combine(day, datetime.min.time()) + timedelta(hours=21)
        cursor = max(probe, day_start) if day_offset == 0 else day_start
        if not busy:
            if cursor + duration <= day_end:
                return cursor
            continue
        for b_start, b_end in busy:
            if cursor + duration <= b_start:
                return cursor
            cursor = max(cursor, b_end)
        if cursor + duration <= day_end:
            return cursor
    return None

def rule_based_suggestions():
    conflicts = check_conflicts()
    all_events = []
    raw = list_events_db()
    for r in raw:
        all_events.append({
            "id": r["id"],
            "title": r["title"],
            "start": datetime.fromisoformat(r["start"]),
            "end": datetime.fromisoformat(r["end"]),
            "place": r["place"]
        })
    suggestions = []
    for a, b in conflicts:
        to_move = b if b["start"] >= a["start"] else a
        keep = a if to_move is b else b
        duration_minutes = int((to_move["end"] - to_move["start"]).total_seconds() // 60)
        slot = find_free_slot(all_events, duration_minutes, after_time=keep["end"])
        if slot:
            new_start = slot
            new_end = slot + timedelta(minutes=duration_minutes)
            reason = f"Resolve overlap with '{keep['title']}'"
        else:
            new_start = keep["end"]
            new_end = keep["end"] + (to_move["end"] - to_move["start"])
            reason = "No free slot in 7 days; suggested immediate after the conflicting event"
        suggestion = {
            "move_event": {
                "id": to_move["id"],
                "title": to_move["title"],
                "start_iso": to_move["start"].isoformat(timespec="minutes"),
                "end_iso": to_move["end"].isoformat(timespec="minutes"),
                "place": to_move.get("place", "")
            },
            "new_start_iso": new_start.isoformat(timespec="minutes"),
            "new_end_iso": new_end.isoformat(timespec="minutes"),
            "reason": reason
        }
        suggestions.append(suggestion)
    return suggestions

# ---------- LLM helper ----------
def llm_explain_suggestion(sugg):
    if not USE_LLM:
        return None
    try:
        llm = ChatOpenAI(model="gpt-4", temperature=0.2)
        template = ChatPromptTemplate.from_messages([
            ("system", "You are an assistant that explains scheduling suggestions briefly and politely."),
            ("human", (
                "Event '{title}' was originally scheduled from {orig_start} to {orig_end}. "
                "We suggest moving it to {new_start} - {new_end} to avoid a conflict. "
            ))
        ])
        formatted = template.format_messages(
            title=sugg["move_event"]["title"],
            orig_start=sugg["move_event"]["start_iso"],
            orig_end=sugg["move_event"]["end_iso"],
            new_start=sugg["new_start_iso"],
            new_end=sugg["new_end_iso"]
        )
        resp = llm.invoke(formatted)
        return resp.content
    except Exception as e:
        return f"(LLM failed: {e})"

# ---------- API Endpoints ----------
@app.on_event("startup")
def startup():
    init_db()

@app.post("/add", response_model=EventOut)
def add_event(e: EventIn):
    try:
        ev_id = add_event_db(e.title, e.start_iso, e.end_iso, e.place)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    return {"id": ev_id, "title": e.title, "start_iso": e.start_iso, "end_iso": e.end_iso, "place": e.place}

@app.get("/events", response_model=List[EventOut])
def get_events():
    rows = list_events_db()
    out = []
    for r in rows:
        out.append(EventOut(id=r["id"], title=r["title"], start_iso=r["start"], end_iso=r["end"], place=r["place"]))
    return out

@app.get("/conflicts", response_model=List[ConflictPair])
def api_conflicts():
    conflicts = check_conflicts()
    out = []
    for a,b in conflicts:
        out.append(ConflictPair(
            a=EventOut(id=a["id"], title=a["title"], start_iso=a["start"].isoformat(timespec="minutes"), end_iso=a["end"].isoformat(timespec="minutes"), place=a.get("place")),
            b=EventOut(id=b["id"], title=b["title"], start_iso=b["start"].isoformat(timespec="minutes"), end_iso=b["end"].isoformat(timespec="minutes"), place=b.get("place"))
        ))
    return out

@app.get("/suggestions", response_model=List[Suggestion])
def api_suggestions():
    sugs = rule_based_suggestions()
    results = []
    for s in sugs:
        llm_text = llm_explain_suggestion(s)
        results.append(Suggestion(
            move_event=EventOut(
                id=s["move_event"]["id"],
                title=s["move_event"]["title"],
                start_iso=s["move_event"]["start_iso"],
                end_iso=s["move_event"]["end_iso"],
                place=s["move_event"].get("place")
            ),
            new_start_iso=s["new_start_iso"],
            new_end_iso=s["new_end_iso"],
            reason=s["reason"],
            llm_explanation=llm_text
        ))
    return results

@app.post("/apply_suggestion")
def api_apply_suggestion(s: Suggestion):
    ev = s.move_event
    update_event_time_db(ev.id, s.new_start_iso, s.new_end_iso)
    return {"status":"ok", "applied_event_id": ev.id}

@app.post("/clear_db")
def api_clear_db():
    clear_db()
    return {"status":"cleared"}
