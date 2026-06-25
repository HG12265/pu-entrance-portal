import random
import queue
import urllib3
import time
from locust import HttpUser, task, between, events, LoadTestShape

# Disable urllib3 warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Statistics tracker for custom metrics
stats = {
    "total_requests": 0,
    "total_failed": 0,
    "500_errors": 0,
    "timeout_errors": 0,
    "db_connection_errors": 0,
}

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    stats["total_requests"] += 1
    response = kwargs.get("response")
    
    if exception:
        stats["total_failed"] += 1
        exc_str = str(exception).lower()
        if "timeout" in exc_str or "time out" in exc_str:
            stats["timeout_errors"] += 1
        elif "connection" in exc_str or "mysql" in exc_str or "conn" in exc_str:
            stats["db_connection_errors"] += 1
            
        if response is not None:
            status_code = getattr(response, "status_code", None)
            if status_code == 500:
                stats["500_errors"] += 1
                resp_text = getattr(response, "text", "").lower()
                if "mysql" in resp_text or "connection" in resp_text or "operationalerror" in resp_text:
                    stats["db_connection_errors"] += 1
            elif status_code in [504, 408]:
                stats["timeout_errors"] += 1
    else:
        if response is not None:
            status_code = getattr(response, "status_code", None)
            if status_code == 500:
                stats["500_errors"] += 1
                stats["total_failed"] += 1
                resp_text = getattr(response, "text", "").lower()
                if "mysql" in resp_text or "connection" in resp_text or "operationalerror" in resp_text:
                    stats["db_connection_errors"] += 1
            elif status_code in [504, 408]:
                stats["timeout_errors"] += 1
                stats["total_failed"] += 1

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    total = stats["total_requests"]
    failed = stats["total_failed"]
    err_rate = (failed / max(1, total)) * 100
    
    print("\n" + "=" * 60)
    print("             EXAM PORTAL LOAD TEST REPORT SUMMARY")
    print("=" * 60)
    print(f"Total Requests Processed : {total}")
    print(f"Failed Requests Count    : {failed}")
    print(f"Overall Request Error %  : {err_rate:.2f}%")
    print(f"500 Internal Server Errs : {stats['500_errors']}")
    print(f"Timeout & Gateway Errs   : {stats['timeout_errors']}")
    print(f"MySQL / DB Conn Errors   : {stats['db_connection_errors']}")
    print("=" * 60 + "\n")

class ExamUser(HttpUser):
    host = "https://localhost:8443"
    # Set wait time between tasks - but we override with manual delay inside the answer loop
    wait_time = between(0.5, 1.5)
    
    # Static queue of candidate credentials (up to 250)
    user_queue = queue.Queue()
    for i in range(1, 251):
        user_queue.put(i)

    def on_start(self):
        # Ignore SSL verification for development certs
        self.client.verify = False
        
        try:
            self.user_idx = self.user_queue.get_nowait()
        except queue.Empty:
            # Recycle or randomize if we exceed 250 concurrent users
            self.user_idx = random.randint(1, 250)
            
        self.app_num = f"LOAD-MCA-{self.user_idx:03d}"
        self.mobile = f"91{self.user_idx:08d}"
        
        self.token = None
        self.attempt_id = None
        self.headers = {}
        self.completed = False

    @task
    def run_exam_simulation(self):
        if self.completed:
            time.sleep(5)
            return

        # 1. Login using application number + mobile
        login_payload = {
            "application_number": self.app_num,
            "mobile_number": self.mobile
        }
        with self.client.post("/api/v1/students/login", json=login_payload, catch_response=True) as response:
            if response.status_code == 200:
                res_json = response.json()
                self.token = res_json["access_token"]
                self.headers = {"Authorization": f"Bearer {self.token}"}
                has_verified = res_json.get("candidate", {}).get("has_verified_details", False)
                response.success()
            else:
                response.failure(f"Login failed for {self.app_num}: {response.text}")
                self.completed = True
                return

        # 2. Verify details if needed
        if not has_verified:
            with self.client.post("/api/v1/students/verify-details", json={"confirm_details": True}, headers=self.headers, catch_response=True) as response:
                if response.status_code == 200:
                    response.success()
                else:
                    response.failure(f"Details verification failed: {response.text}")
                    self.completed = True
                    return

        # 3. Fetch active exam/instructions
        with self.client.get("/api/v1/exams/active", headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Active exam fetch failed: {response.text}")
                self.completed = True
                return

        # 4. Start exam
        with self.client.post("/api/v1/exams/start", headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                start_data = response.json()
                self.attempt_id = start_data["attempt_id"]
                questions = start_data["questions"]
                response.success()
            else:
                response.failure(f"Start exam failed: {response.text}")
                self.completed = True
                return

        # 5. Answer 100 questions with random delays
        # Simulate refresh for 20% of users
        simulate_refresh = random.random() < 0.20
        refresh_after_q = 50
        answers_saved = {}

        for idx, q in enumerate(questions):
            q_id = q["id"]
            selected_option = random.choice(["A", "B", "C", "D"])
            answers_saved[q_id] = selected_option

            payload = {
                "attempt_id": self.attempt_id,
                "question_id": q_id,
                "selected_option": selected_option
            }

            # Save answer
            with self.client.post("/api/v1/exams/save-answer", json=payload, headers=self.headers, catch_response=True) as response:
                if response.status_code == 200:
                    response.success()
                else:
                    response.failure(f"Save answer failed for QID {q_id}: {response.text}")

            # Every 25 questions, call update-index
            if (idx + 1) % 25 == 0:
                idx_payload = {
                    "attempt_id": self.attempt_id,
                    "current_question_index": idx
                }
                with self.client.post("/api/v1/exams/update-index", json=idx_payload, headers=self.headers, catch_response=True) as response:
                    if response.status_code == 200:
                        response.success()
                    else:
                        response.failure(f"Update index failed at question index {idx}: {response.text}")

            # Simulate refresh at midpoint by calling start again and verifying answers are preserved
            if simulate_refresh and (idx + 1) == refresh_after_q:
                with self.client.post("/api/v1/exams/start", headers=self.headers, catch_response=True) as response:
                    if response.status_code == 200:
                        res_data = response.json()
                        db_answers = res_data.get("answers", {})
                        
                        # Verify all answered questions so far are correctly preserved in response
                        all_match = True
                        for q_key, ans_val in answers_saved.items():
                            if db_answers.get(str(q_key)) != ans_val:
                                all_match = False
                                break
                                
                        if all_match:
                            response.success()
                        else:
                            response.failure("Refresh answer validation failed: answers missing or mismatched.")
                    else:
                        response.failure(f"Refresh start exam call failed: {response.text}")

            # Random delay between answers: 0.5 to 3 seconds
            time.sleep(random.uniform(0.5, 3.0))

        # 6. Submit exam
        submit_payload = {
            "attempt_id": self.attempt_id,
            "submit_source": "manual",
            "submitted_reason": "load test student submission"
        }
        with self.client.post("/api/v1/exams/submit", json=submit_payload, headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Submit exam failed: {response.text}")
                self.completed = True
                return

        # 7. Fetch result
        with self.client.get("/api/v1/results/my-results", headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Fetch my-results failed: {response.text}")

        self.completed = True

# Automated load stages: 50 -> 150 -> 250 concurrent users
class StagesShape(LoadTestShape):
    stages = [
        {"duration": 180, "users": 50, "spawn_rate": 5},    # Stage 1: 50 users (3 minutes)
        {"duration": 360, "users": 150, "spawn_rate": 10},  # Stage 2: 150 users (6 minutes total)
        {"duration": 540, "users": 250, "spawn_rate": 10},  # Stage 3: 250 users (9 minutes total)
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return stage["users"], stage["spawn_rate"]
        return None
