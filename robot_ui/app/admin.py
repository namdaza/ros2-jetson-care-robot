import os

def check_password(pw: str) -> bool:
    expected_pw = os.getenv("ADMIN_PASSWORD", "0000")
    return pw == expected_pw