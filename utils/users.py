from queue import Queue
import random

user_pool = [
    {
        "email": "locust01@hisawyer.com",
        "password": "password123",
        "requires_2fa": True,
        "totp_secret": "MZGXM32KOU2HA4KNIQZUCNCBNJYE6UBV",
    }
] + [
    {
        "email": f"locust{i:02d}@hisawyer.com",
        "requires_2fa": False,
        "password": "password123",
    }
    for i in range(2, 5)
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
