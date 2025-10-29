from locust import SequentialTaskSet, task, between, events
from utils.auth import login
from utils.users import get_unique_user
import time
import random


class MarketplaceTasksScenario(SequentialTaskSet):
    wait_time = between(1, 5)

    # def on_start(self):
    #     self.user = get_unique_user()

    #     try:
    #         self.csrf_token = login(
    #             client=self.client,
    #             user=self.user,
    #             require_2fa=self.user.get("requires_2fa", False),
    #             totp_secret=self.user.get("totp_secret", None) if self.user.get("requires_2fa") else None
    #         )
    #         print(f"{self.user['email']} ready for load testing")
    #     except Exception as e:
    #         print(f"✗ Login failed for {self.user['email']}: {e}")
    #         self.environment.runner.quit()

    @task
    def browse_marketplace(self):
        user = self.user.user
        time.sleep(random.uniform(1, 10))
        csrf_token = login(self.client, user, user.get("requires_2fa", False), user.get("totp_secret", None))

        time.sleep(random.uniform(1, 10))
        print("going to marketplace")
        self.client.get("/marketplace")


@events.quitting.add_listener
def on_quit(environment, **kwargs):
    """Cleanup when test ends"""
    print("✓ Load test completed")
