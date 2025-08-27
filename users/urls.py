from django.urls import path
from .views import *

urlpatterns = [
    path("verify-token/", verify_firebase_token, name="verify_token"),
    path("send-otp/", send_otp, name="send_otp"),
    path("verify-otp/", verify_otp, name="verify_otp"),
    path("current-user/", current_user, name="current_user"),
    path("logout/", logout_user, name="logout_user"),
]
