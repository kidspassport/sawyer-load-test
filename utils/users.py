from queue import Queue
import random

user_pool = [
    {
        "email": f"locust{i:02d}@example.com",
        "password": "password123",
    }
    for i in range(1, 101)
]

user_queue: Queue = Queue()
for user in user_pool:
    user_queue.put(user)


def get_random_user():
    return random.choice(user_pool)


def get_unique_user():
    if user_queue.empty():
        raise Exception("No more unique users available.")
    return user_queue.get()
