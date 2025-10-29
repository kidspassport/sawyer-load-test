from locust import SequentialTaskSet, task
from datetime import datetime
import os
import json
import random
import time
from urllib.parse import urlencode

from utils.auth import extract_csrf_token, login


class VisitWidgetScenario(SequentialTaskSet):
    def on_start(self):
        self.slug = self.user.environment.parsed_options.slug

    @task
    def visit_widget(self):
        time.sleep(random.uniform(1, 10))
        user = self.user.user # ... why is this needed again?
        csrf_token = login(self.client, user)

        now = datetime.now()
        html_headers = {"Accept": "text/html"}
        json_headers = {"Accept": "application/json"}

        number_of_ages = random.choice(range(1, 10))
        age_ranges = random.sample(range(11, 31), k=number_of_ages)
        month = random.randint(1, 12)
        year = now.year
        time_picker_min = random.randint(21600, 40000)
        time_picker_max = random.randint(75000, 90000)
        adults_only = random.choice([0, 1])

        self.client.get(  # Load widget calendar view
            f"/{self.slug}/schedules/widget_calendar",
            headers=html_headers
        )

        self.client.get(  # Load widget calendar view with time filters
            self._build_widget_calendar_filter_url({
                "month": month,
                "year": year,
                "time_picker_max": time_picker_max,
                "time_picker_min": time_picker_min
            }),
            headers=html_headers
        )

        time.sleep(random.uniform(1, 10))

        self.client.get(  # Clear the filters
            f"/{self.slug}/schedules/widget_calendar",
            headers=html_headers
        )

        time.sleep(random.uniform(1, 10))

        self.client.get(  # Load widget calendar view with age filters & time filters
            self._build_widget_calendar_filter_url({
                "month": month,
                "year": year,
                "time_picker_max": time_picker_max,
                "time_picker_min": time_picker_min,
                "age_ranges": age_ranges,
                "adults_only": adults_only
            }),
            headers=html_headers
        )

        time.sleep(random.uniform(1, 10))

        self.client.get(  # Visit widget list view
            f"/{self.slug}/schedules",
            headers=html_headers
        )

        scheduled_activities = self.client.get(  # Load data for widget list view
            f"/api/v1/widget/scheduled_activities?slug={self.slug}&page=1",
            headers=json_headers
        )

        data = json.loads(scheduled_activities.text) # TODO drawing an error here: JSONDecodeError("Expecting value", s, err.value) from Nonejson.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
        results = data.get("data", {}).get("results", [])
        asg_id = results[0]["id"] if results else None

        time.sleep(random.uniform(1, 10))

        self.client.get(  # Load widget list view w/ filters
            self._build_widget_filter_url({
                "time_picker_max": time_picker_max,
                "time_picker_min": time_picker_min,
                "age_ranges": age_ranges
            }),
            headers=html_headers
        )

        time.sleep(random.uniform(1, 10))

        self.client.get(  # Visit widget list view
            f"/{self.slug}/schedules",
            headers=html_headers
        )

        if asg_id:
            self.client.get(  # Visit PDP from widget
                f"/{self.slug}/schedules/activity-set/{asg_id}?source=semesters"
            )

    def _build_widget_calendar_filter_url(self, params):
        return f"/{self.slug}/schedules/widget_calendar?{urlencode(params, doseq=True)}"

    def _build_widget_filter_url(self, params):
        return f"/{self.slug}/schedules?{urlencode(params, doseq=True)}"
