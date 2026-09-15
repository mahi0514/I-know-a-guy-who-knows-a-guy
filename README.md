# ConnectApp — MVP

A minimal social app for finding the shortest connection path between two
people: "how is Person A connected to Person C?" → shows A → B → C.

## What's included

- `backend/app.py` — Flask server: profiles, connections, and BFS path search.
  Also serves the frontend, so this is the only thing you run.
- `backend/schema.sql` — PostgreSQL version of the schema, for when you
  outgrow SQLite (not needed to run the MVP).
- `frontend/index.html` — single-page UI (plain HTML/CSS/JS, no build step).

## Run it locally

```
cd backend
pip install flask --break-system-packages
python app.py
```

Then open **http://localhost:5000** in a browser.

That's it — no separate frontend server needed. The Flask app serves the UI
directly.

## Try it

1. Create 3–4 profiles under "Create a profile"
2. Connect them under "Add a connection" (e.g. A↔B, B↔C)
3. Search "How am I connected to...?" for A → C — you'll see the path and
   degrees of separation

## Sharing this with others to test

The simplest way to let other people try it without setting anything up
locally is to deploy it on a free host:

- **Render** (render.com) — free tier, connect your GitHub repo, it runs
  `python app.py` automatically
- **Railway** (railway.app) — similar, free tier, very quick setup
- **PythonAnywhere** — free tier aimed at exactly this kind of small Flask app

All three: push this folder to a GitHub repo, connect the repo on the host,
and they give you a public URL to share.

## Known limitations (by design, for the MVP)

- Single shared database — everyone who uses the hosted link sees the same
  users/connections (fine for a demo; would need real accounts/auth for a
  real launch)
- No login/auth yet — anyone can create profiles or connections
- BFS runs on the full graph in memory each search — fine for hundreds or
  low thousands of users, would need optimization at real social-network scale

## Natural next steps

- Add simple auth (so people manage their own profile)
- Deploy publicly so you can send the link to friends/testers
- Add a graph visualization (not just the chain view) once you have real data
  to show off
