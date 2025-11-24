from queue import Queue
import random

user_pool = [
    {
        "email": "locust_01@hisawyer.com",
        "password": "password123",
        "requires_2fa": True,
        "totp_secret": "PBXG6SDLJI2VEM3SJBSVKN2DNFKWQ3TF",
    },
    {
        "email": "locust_02@hisawyer.com",
        "password": "password123",
        "requires_2fa": True,
        "totp_secret": "IJYEMUCVNZXEI6CHGZUWUUTBKZCUSVDB",
    },
    {
        "email": "locust_03@hisawyer.com",
        "password": "password123",
        "requires_2fa": True,
        "totp_secret": "NZHWGSDNI5CTCTLBGM3WQUTIOVHUMULY",
    },
    {
        "email": "locust_04@hisawyer.com",
        "password": "password123",
        "requires_2fa": True,
        "totp_secret": "O5ZUC4SRGF4HIN3QORUXOTSXIFLXIMRT",
    },
    {
        "email": "locust_05@hisawyer.com",
        "password": "password123",
        "requires_2fa": True,
        "totp_secret": "MUYG23BSJZUW6QTZIJXEW6TPJI2UQ3TY",
    },
    {
        "email": "locust_06@hisawyer.com",
        "password": "password123",
        "requires_2fa": True,
        "totp_secret": "GFWEKTT2KFCEGN3IHFBESUCPGA2USSKP",
    },
    {
        "email": "locust_07@hisawyer.com",
        "password": "password123",
        "requires_2fa": True,
        "totp_secret": "MZBE4MKHGJJTENBXIY3HM4KCKNLGM4LX",
    },
    {
        "email": "locust_08@hisawyer.com",
        "password": "password123",
        "requires_2fa": True,
        "totp_secret": "MJTVMULTNZKUYTKBGE4WYMSWOU4EOUBT",
    },
    {
        "email": "locust_09@hisawyer.com",
        "password": "password123",
        "requires_2fa": True,
        "totp_secret": "MJ2WE5RQHA3WK4KKGNIG2Y2INRSXARTV",
    },
    {
        "email": "locust_10@hisawyer.com",
        "password": "password123",
        "requires_2fa": True,
        "totp_secret": "MZ3WSQ3NJVFDONLJINHUSODRNE4GKULN",
    },
] + [
    {
        "email": f"locust_{i:02d}@hisawyer.com",
        "requires_2fa": False,
        "password": "password123",
    }
    for i in range(11, 1000)
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
