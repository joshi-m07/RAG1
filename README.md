# Reminder Agent – Streamlit Frontend

This is a Streamlit UI for a Reminder Agent – Task Scheduling project. It connects to a FastAPI backend via HTTP.

## Features

- Add/Update/Delete tasks with datetime picker
- View tasks in card/table style with mark-as-done
- Today’s schedule dashboard, highlights tasks due within 1 hour
- Sidebar navigation and configurable API base URL

## Requirements

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run

Set the API base URL if different from default `http://localhost:8000`:

```bash
set API_BASE_URL=http://localhost:8000
```

Then start Streamlit:

```bash
streamlit run Frontendapp.py
```

Use the sidebar to navigate. You can also override the API endpoint in the sidebar.

### backend (for local testing)


```bash
uvicorn BACKEND:app --host 0.0.0.0 --port 8000 --reload
```

Then run Streamlit in another terminal and keep the API Base URL as `http://localhost:8000`.
run your BACKEND.py as http://127.0.0.1:8000/,

## Expected Backend Endpoints

- POST `/tasks`
- GET `/tasks`
- PUT `/tasks/{id}`
- DELETE `/tasks/{id}`
- GET `/tasks/today`



Team Numbers:

1.K.Deepa Shree(22N213)

2.Joshika M(22N226)

3.Pavithra E(22N236)

4.PriyaDharshini(22N240)

5.Vijaya Varshini(22N265)



