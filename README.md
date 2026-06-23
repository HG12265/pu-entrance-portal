# Periyar University Entrance Examination Portal

A premium PG entrance examination portal with a secure FastAPI backend and a beautiful glassmorphic React (Vite) frontend. Includes anti-cheat proctoring rules, real-time auto-saving, dynamic leaderboard compilation, and bulk question spreadsheet uploading.

---

## 🛠️ Environment Configuration

Configuration variables for both frontend and backend are centralized in `.env` files. Both environments include `.env.example` templates which show the variables needed.

### 1. Backend Setup (`backend/`)
1. Change directory into the backend project:
   ```bash
   cd backend
   ```
2. Copy the configuration template to `.env`:
   ```bash
   copy .env.example .env
   ```
3. Open `backend/.env` in your editor and configure:
   - `DATABASE_PASSWORD`: Password for your MySQL connection.
   - `JWT_SECRET_KEY`: A strong, unique key for session encryption.
   - `ADMIN_USERNAME` and `ADMIN_PASSWORD`: Credentials for seeding the default administrator account.

> [!WARNING]
> **Production Safety Safeguard**: In production (`ENVIRONMENT="production"`), backend initialization will fail to start if the database password, JWT secret, or admin credentials are empty, default, or weak. Make sure to generate strong values.

### 2. Frontend Setup (`frontend/`)
1. Change directory into the frontend project:
   ```bash
   cd frontend
   ```
2. Copy the configuration template to `.env`:
   ```bash
   copy .env.example .env
   ```
3. Open `frontend/.env` and review:
   - `VITE_API_BASE_URL`: Base URL of the running FastAPI server (defaults to `http://localhost:8000`).

> [!IMPORTANT]
> **Vite Environment Variable Visibility**: Vite prefixes variables with `VITE_` to bundle them into public browser assets. **Never** write database credentials, JWT secrets, or administrative passwords in `frontend/.env`.

---

## 🚀 Running the Application

### 1. Database Initialization
Before running the application, make sure your MySQL service is active and the database is configured. Initialize database tables and seed the admin user:
```bash
cd backend
python init_db.py
```

### 2. Start the Backend Server
Launch the FastAPI development server:
```bash
cd backend
uvicorn app.main:app --reload
```
The API documentation is accessible at: `http://localhost:8000/docs`.

### 3. Start the Frontend Server
Install dependencies and run the Vite server:
```bash
cd frontend
npm install
npm run dev
```
Open your browser and navigate to the developer server address (usually `http://localhost:5173`).
To access the administrative panel directly, navigate to `http://localhost:5173/admin/login` and log in with your seeded administrator credentials.

---

## 🔒 Security Policy and Rules

- **Never Commit `.env` Files**: Local environment configurations (`.env`) contain secrets and passwords. They must never be checked into version control. Only commit `.env.example` templates.
- **Frontend Environmental Exposure**: Frontend parameters (prefixed with `VITE_`) are compiled into public browser assets and visible to anyone inspecting the client code. **Do not** write database credentials, admin credentials, JWT secrets, or private configurations in `frontend/.env`.
- **Change Default Admin Credentials**: Always change the default seeding username/password (`ADMIN_USERNAME` and `ADMIN_PASSWORD`) to strong, unique values before running or deploying in production or staging environments.

---

## 🐳 Running via Docker Compose

You can containerize the database, backend, and frontend services using Docker Compose.

### 1. Configure the Environment
Copy the root environment template to `.env`:
```bash
copy .env.example .env
```
Open `.env` in the root directory and specify your custom root database password, user passwords, administrative seed credentials, and JWT encryption keys.

### 2. Start all Containers
Build the images and run the services:
```bash
docker compose up --build
```
This command spins up:
- **Database (db)**: MySQL 8.0 mapped to port `3306`.
- **Backend (FastAPI)**: Server running on port `8000`.
- **Frontend (Nginx / React)**: App accessible at `http://localhost:8080`.

### 3. Service Access Endpoints
- **Student Exam Portal**: `https://localhost:8443/` (or HTTP redirect at `http://localhost:8080/`)
- **Admin Dashboard**: `https://localhost:8443/admin/login`
- **FastAPI API Swagger Docs**: `http://localhost:8000/docs`

### 4. HTTPS and SSL Certificate Setup
To serve the portal securely over HTTPS (`https://localhost:8443`), you must generate SSL certificate keys. 

For **local testing and demonstration**, you can generate a self-signed SSL certificate key pair:
- **Git Bash / Terminal / PowerShell command**:
  ```bash
  openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout nginx/certs/server.key -out nginx/certs/server.crt -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
  ```
- Make sure to run this command from the root workspace folder to place files inside `nginx/certs/`.
- Nginx is configured to redirect HTTP (`http://localhost:8080`) to HTTPS (`https://localhost:8443`) automatically. Accept the self-signed certificate warning in your browser to proceed to the portal.

> [!WARNING]
> Self-signed certificates are only for local development testing. Production environments must replace `server.crt` and `server.key` inside `nginx/certs/` with official certificates from a trusted Certificate Authority (e.g. Let's Encrypt / Certbot).

### 5. Production Rate Limiting Notice
The API limits automated requests:
- **Student Registration**: 10 requests per minute.
- **Admin Login**: 5 requests per minute.

> [!NOTE]
> SlowAPI's default in-memory rate limiter is suitable for local/demo usage. For real production environments running multiple workers or container replicas, configure a Redis-backed rate limit storage backend inside `app/limiter.py` to maintain consistent rate-limiting across instances.

### 6. Tear Down & Database Reset
- **Stop services**:
  ```bash
  docker compose down
  ```
- **Reset database volumes** (wipes all student and attempts records for a fresh install):
  ```bash
  docker compose down -v
  ```

---

## ⚠️ Development Database Clean Utility (`clear_db.py`)

The root directory contains a database reset utility `clear_db.py` that clears all tables and seeds default courses (MCA, M.Sc CS, M.Sc DS) and the default administrator user.

> [!CAUTION]
> **Production Protection Warning**: **Never** run `clear_db.py` in production or staging environments with real student data. Doing so will permanently delete all registration records, student applications, exam attempts, and answer logs.
>
> The script will check the `ENVIRONMENT` variable and refuse to execute if set to `production`, `prod`, or `staging`.



