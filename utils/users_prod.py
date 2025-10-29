from queue import Queue
import random

user_pool = [
    {
        "email": "locust_01@hisawyer.com",
        "password": "password123",
        "requires_2fa": True,
        "totp_secret": "ON4GMTCPKB4WE3DBHBLDS6LYKR2GC32G",
    },
    {
        "email": "locust_02@hisawyer.com",
        "password": "password123",
        "requires_2fa": True,
        "totp_secret": "KZVDKQTDJRZWWYKKIFSFGT3QMFXDEZ3V",
    },
    {
        "email": "locust_03@hisawyer.com",
        "password": "password123",
        "requires_2fa": True,
        "totp_secret": "O5YFK3JRJRVXQUTJGI4DGS2UM5CHUYTC",
    },
    {
        "email": "locust_04@hisawyer.com",
        "password": "password123",
        "requires_2fa": True,
        "totp_secret": "KNEDQ2BQOVVHQN3HKNXW2NKIMVTXM3SQ",
    },
    {
        "email": "locust_05@hisawyer.com",
        "password": "password123",
        "requires_2fa": True,
        "totp_secret": "M5FEORTOK54EONCQKBEUK2LBOE2VEVCB",
    },
    {
        "email": "locust_06@hisawyer.com",
        "password": "password123",
        "requires_2fa": True,
        "totp_secret": "KBSGKMLUMRKUYULONRKDE4DTOZ3VKQTX",
    },
    {
        "email": "locust_07@hisawyer.com",
        "password": "password123",
        "requires_2fa": True,
        "totp_secret": "INDW233VINVDAM3EKVYFATDCG5IXAUKQ",
    },
    {
        "email": "locust_08@hisawyer.com",
        "password": "password123",
        "requires_2fa": True,
        "totp_secret": "MMZWOQKTN5UGC5BVIZDEI3KLONRWCRDC",
    },
    {
        "email": "locust_09@hisawyer.com",
        "password": "password123",
        "requires_2fa": True,
        "totp_secret": "GZRVKZDIMZTHKY2VJU3WY4BUMY4W6VLY",
    },
    {
        "email": "locust_10@hisawyer.com",
        "password": "password123",
        "requires_2fa": True,
        "totp_secret": "JY2DGTRQMJHEYV3NGU3GYTRZJNEUOQLI",
    },
]
# + [
#     {
#         "email": f"locust_{i:02d}@hisawyer.com",
#         "requires_2fa": False,
#         "password": "password123",
#     }
#     for i in range(11, 600)
# ]


user_queue: Queue = Queue()
for user in user_pool:
    user_queue.put(user)


def get_random_user():
    return random.choice(user_pool)


def get_unique_user():
    if user_queue.empty():
        raise Exception("No more unique users available.")
    return user_queue.get()
