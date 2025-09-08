import os
from locust import HttpUser, task, between

class WebsiteUser(HttpUser):
    """
    Simulates a user interacting with the SMART on FHIR application.
    """
    wait_time = between(1, 5)  # Simulate user waiting 1-5 seconds between tasks

    def on_start(self):
        """
        This method is called when a new user is started.
        We will use a session cookie from an environment variable for authentication.
        
        **Instructions for Test Execution:**
        1. Manually log in to the application through a browser.
        2. Use browser developer tools to find the value of the 'session' cookie.
        3. Set this value as an environment variable named 'LOCUST_SESSION_COOKIE'
           and the patient ID as 'LOCUST_TEST_PATIENT_ID' before running Locust.
        """
        self.session_cookie = os.environ.get("LOCUST_SESSION_COOKIE")
        self.patient_id = os.environ.get("LOCUST_TEST_PATIENT_ID")

        if not self.session_cookie or not self.patient_id:
            print("="*80)
            print("ERROR: Environment variables LOCUST_SESSION_COOKIE and LOCUST_TEST_PATIENT_ID must be set.")
            print("Please follow the instructions in the on_start method.")
            print("="*80)
            self.environment.runner.quit()
            return
            
        # Manually set the Cookie header for each request.
        self.cookie_header = f"session={self.session_cookie}"

    @task
    def calculate_risk(self):
        """
        Simulates a user calculating the PRECISE-DAPT risk score.
        """
        if self.patient_id:
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                # Manually inject the Cookie header into every request.
                'Cookie': self.cookie_header
            }
            payload = {
                "patientId": self.patient_id,
                # Add other parameters required by the API if any
            }
            self.client.post(
                "/api/calculate_risk",
                json=payload,
                headers=headers,
                name="/api/calculate_risk"  # Group all such requests under this name in stats
            )
