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

---

## 🏫 Counselling Seat Matrix & Reservation Modes

The portal includes an official community-wise seat matrix with support for order-independent community normalization and two distinct reservation/counselling modes:

### 1. Official Course Capacities
- **MCA** (30 seats): OC=9, BC=8, BCM=1, MBC=6, SC=4, ST=1, SCA=1.
- **M.Sc Computer Science** (44 seats): OC=14, BC=12, BCM=2, MBC=9, SC=5, SCA=1, ST=1.
- **M.Sc Data Science** (44 seats): OC=14, BC=12, BCM=2, MBC=9, SC=5, ST=1, SCA=1.

### 2. Counselling Modes
The active mode is configured via the `COUNSELLING_MODE` environment variable in the backend:
- **`SIMPLE_COMMUNITY_QUOTA`**: Candidates compete strictly within their respective community quota seat allocation limits.
- **`OPEN_COMPETITION_THEN_QUOTA`**: First, OC (Open Competition) seats are filled by the top overall candidates regardless of their community. Then, remaining candidates compete within their respective community quota seats.

Administrators can edit the seat matrix dynamically in the **Config Settings** tab on the Admin Dashboard, which performs real-time validation to ensure the sum of community seats matches the total course capacity. The **Counselling & Rankings** tab displays the computed original rank, active rank, community rank, community quota seat count, selection bucket, and counselling status.

---

## 🧪 Mock Counselling Filter Test Data

For local development and testing, you can seed a mock dataset designed to verify open competition, community allocation, and multi-course candidate exclusions.

### 1. Seed Mock Counselling Data
To populate mock candidates, applications, and submitted attempts for MCA and M.Sc CS, run the seeder:
```bash
docker compose exec backend python app/seed_mock_counselling_data.py
```
To clear previous mock records first:
```bash
docker compose exec backend python app/seed_mock_counselling_data.py --delete-existing-mock
```

### 2. Verify Counselling Filters
To run automated filter and selection assertions (checking OC/BC/MBC/SC/SCA/ST buckets, shared candidate exclusion logic, etc.), execute:
```bash
docker compose exec backend python app/verify_mock_counselling_filters.py
```

---

## 🧹 Cleanup Operational Data Only

For resetting student, registration, attempt, and answer data while preserving system courses, admin logins, seat configurations, and exam rules, use the operational cleanup script.

### 1. Dry Run (View current operational and config counts)
```bash
docker compose exec backend python app/cleanup_operational_data.py
```

### 2. Confirmed Deletion
```bash
docker compose exec backend python app/cleanup_operational_data.py --confirm
```

---

## 🧪 Load Testing & Data Integrity Verification Runbook

Follow these steps to perform load testing for 150 concurrent exam users and verify data integrity:

### 1. Build and Start the Environment
Make sure all services are built and running:
```bash
docker compose up --build -d
```

### 2. Seed Mock Load Test Students
Seed 250 load testing candidates with course MCA, verification details enabled, random marks, and ensure exactly 100 questions (25 per section) are active in the database:
```bash
docker compose exec backend python app/seed_load_test_students.py --count 250
```

### 3. Run the Load Test with Locust
Install Locust and run the load test on the secure HTTPS server:
```bash
# Install Locust if not already installed:
pip install locust

# Run the test (using 'python -m locust' avoids PATH issues on Windows):
python -m locust -f load_tests/locustfile.py --host=https://localhost:8443
```
This will automate the load stages (50 -> 150 -> 250 concurrent users) and record request statistics (average, p95, p99 response times, error rates, timeout errors, 500 errors, and database connection errors). Upon termination, a summary report will be logged to the console.

### 4. Verify Exam Data Integrity
After the load test completes, verify database constraints, scoring correctness, and counseling rankings:
```bash
docker compose exec backend python app/verify_exam_data_integrity.py
```
This verifies that every load test user has exactly one attempt, 100 answers, no duplicate entries, correct score calculations, no stuck attempts, and that counselling rankings compile without error.




