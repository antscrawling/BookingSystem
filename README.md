# Badminton Court Booking Backend

FastAPI CRUD backend for a badminton court reservation system.

## Business Rules

- Price is `$12` per hour.
- Opening hour is `08:00`.
- Closing hour is `22:00`.
- Total courts available: `10` (`court_number` must be `1` to `10`).
- A booking cannot overlap another booking on the same date and court.

## Tech Stack

- FastAPI (backend API)
- SQLite (simple SQL database in `bookings.db`)
- SQLAlchemy ORM

## Install

```bash
pip install -e .
```

## Share Package Via Git

### 1) Install Git

macOS (Homebrew):

```bash
brew install git
```

Windows:

- Install Git for Windows from https://git-scm.com/download/win

Ubuntu/Debian:

```bash
sudo apt update
sudo apt install -y git
```

Verify:

```bash
git --version
```

### 2) Create Git Repository (Local Instance)

From project root:

```bash
git init
git add .
git commit -m "Initial booking system"
```

### 3) Publish To GitHub (Remote Instance)

Create an empty repository on GitHub, then run:

```bash
git branch -M main
git remote add origin https://github.com/antscrawling/BookingSystem.git
git push -u origin main
```

### 4) How Users Get And Install Your Project

Clone then run:

```bash
git clone https://github.com/<your-user>/<your-repo>.git
cd <your-repo>
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn src.main:app --reload
```

Windows PowerShell activation:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Run

```bash
uvicorn src.main:app --reload
```

Server URL: `http://127.0.0.1:8000`
Swagger docs: `http://127.0.0.1:8000/docs`

## API Endpoints

- `GET /` - service info and booking rules
- `GET /admin/settings` - read current runtime settings
- `PUT /admin/settings` - update price, opening/closing hours, and court count
- `POST /bookings` - create booking
- `GET /bookings` - list all bookings
- `GET /bookings/{booking_id}` - get booking by id
- `PUT /bookings/{booking_id}` - update booking
- `DELETE /bookings/{booking_id}` - delete booking

You can filter list endpoint with query params:

- `booking_date=YYYY-MM-DD`
- `court_number=1..10`

## Example Create Request

```json
{
	"customer_name": "John Doe",
	"court_number": 3,
	"booking_date": "2026-06-07",
	"start_hour": 9,
	"duration_hours": 2
}
```

Expected computed amount: `2 * 12 = 24`

## Update Price/Hours/Courts At Runtime

You can change settings without editing code. The frontend reads these rules from `GET /` on load.

```json
PUT /admin/settings
{
	"price_per_hour": 15,
	"opening_hour": 8,
	"closing_hour": 22,
	"total_courts": 10
}
```

After this, new booking calculations in the frontend and backend use the updated values.

## Node.js Frontend Integration

This API enables CORS for all origins, so a Node.js frontend can call it directly during development.

## Frontend (Node.js)

A simple Node.js frontend is included in `frontend/`.

### Start Backend

```bash
uvicorn src.main:app --reload
```

### Start Frontend

```bash
cd frontend
npm start
```

Frontend URL: `http://127.0.0.1:3000`

The UI supports:

- Create booking
- View booking list
- Filter by date and court
- Update booking
- Delete booking

## Windows Setup

### 1) Install Prerequisites

- Install Python 3.11+ from python.org
- Install Node.js LTS from nodejs.org (includes npm)

### 2) Backend Setup (PowerShell)

```powershell
cd C:\path\to\BookingSystem
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
uvicorn src.main:app --reload
```

### 3) Backend Setup (Command Prompt)

```bat
cd C:\path\to\BookingSystem
python -m venv .venv
.venv\Scripts\activate.bat
pip install -e .
uvicorn src.main:app --reload
```

### 4) Frontend Setup (PowerShell or Command Prompt)

Open a second terminal:

```bat
cd C:\path\to\BookingSystem\frontend
npm install
npm start
```

### 5) Open the App

- Frontend: `http://127.0.0.1:3000`
- Backend API: `http://127.0.0.1:8000`
- API docs: `http://127.0.0.1:8000/docs`

## Windows Troubleshooting

### PowerShell: "running scripts is disabled"

If activation fails with execution policy errors:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then close and reopen PowerShell, and activate again:

```powershell
.\.venv\Scripts\Activate.ps1
```

### `python` command not found

- Reinstall Python from python.org and enable **Add Python to PATH** during install.
- Or use the launcher command:

```powershell
py -3 --version
```

### `uvicorn` not recognized

Usually the virtual environment is not active or dependencies are not installed.

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e .
uvicorn src.main:app --reload
```

### `npm` or `node` not recognized

- Reinstall Node.js LTS from nodejs.org.
- Open a new terminal and verify:

```powershell
node -v
npm -v
```

### Frontend fails with missing packages

From `frontend` folder, install dependencies first:

```powershell
cd C:\path\to\BookingSystem\frontend
npm install
npm start
```

### Port already in use (8000 or 3000)

Run backend/frontend on different ports:

```powershell
uvicorn src.main:app --reload --port 8001
```

```powershell
cd C:\path\to\BookingSystem\frontend
set PORT=3001
npm start
```

Then open the matching URLs (for example `http://127.0.0.1:3001`) and set the frontend API URL field to `http://127.0.0.1:8001`.

### App cannot connect to API

- Confirm backend is running and `http://127.0.0.1:8000/docs` opens.
- In frontend, ensure FastAPI URL is exactly `http://127.0.0.1:8000` (or your chosen port).
- Restart both servers after changing settings.
