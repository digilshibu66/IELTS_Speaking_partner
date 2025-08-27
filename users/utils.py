import random
from rest_framework_simplejwt.tokens import RefreshToken
def generate_otp():
    return str(random.randint(100000, 999999))  # 6-digit OTP

def generate_jwt(user):
    refresh = RefreshToken.for_user(user)
    user.jwt_access = str(refresh.access_token)
    user.jwt_refresh = str(refresh)
    user.save()
    return str(refresh.access_token), str(refresh)