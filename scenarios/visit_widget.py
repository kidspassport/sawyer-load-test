from locust import SequentialTaskSet, task
from datetime import datetime
import os
from bs4 import BeautifulSoup
import json

class VisitWidgetScenario(SequentialTaskSet):
    def on_start(self):
        self.slug = self.user.environment.parsed_options.slug

    @task
    def visit_widget(self):
        now = datetime.now()

        self.client.get(  # Load widget calendar view
            f"/{self.slug}/schedules/widget_calendar",
            headers={"Accept": "text/html"}
        )

        self.client.get(  # Load widget calendar view with time filters
            f"/{self.slug}/schedules/widget_calendar?month={now.month}&year={now.year}&time_picker_max=77400&time_picker_min=25200",
            headers={"Accept": "text/html"}
        )

        self.client.get(  # Clear the filters
            f"/{self.slug}/schedules/widget_calendar",
            headers={"Accept": "text/html"}
        )

        self.client.get(  # Load widget calendar view with age filters & time filters
            f"/{self.slug}/schedules/widget_calendar?slug={self.slug}&month=6&year=2025&age_ranges%5B%5D=11&age_ranges%5B%5D=14&age_ranges%5B%5D=20&age_ranges%5B%5D=21&age_ranges%5B%5D=23&adults_only=1&time_picker_max=84600&time_picker_min=21600",
            headers={"Accept": "text/html"}
        )

        self.client.get(  # Visit widget list view
            f"/{self.slug}/schedules",
            headers={"Accept": "text/html"}
        )

        scheduled_activities = self.client.get(  # Load data for widget list view
            f"/api/v1/widget/scheduled_activities?slug={self.slug}&page=1",
            headers={"Accept": "application/json"}
        )

        data = json.loads(scheduled_activities.text)
        results = data.get("data", {}).get("results", [])
        asg_id = results[0]["id"] if results else None

        filters_url = f"/{self.slug}/schedules?slug={self.slug}&age_ranges%5B%5D=15&age_ranges%5B%5D=16&age_ranges%5B%5D=22&age_ranges%5B%5D=23&time_picker_max=84600&time_picker_min=21600"

        self.client.get(  # Load widget list view w/ filters
            filters_url,
            headers={}
        )

        if asg_id:
            self.client.get(  # Visit PDP from widget
                f"/{self.slug}/schedules/activity-set/{asg_id}?source=semesters"
            )



