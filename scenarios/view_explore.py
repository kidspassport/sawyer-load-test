from locust import task

@task
def view_explore(self):
    self.client.get("/explore")
