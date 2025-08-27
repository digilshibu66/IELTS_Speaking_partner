import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
from django.core.cache import cache
from django.contrib.auth import logout
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import User
from .serializers import UserSerializer
from .utils import generate_jwt, generate_otp

# Initialize Firebase Admin
if not firebase_admin._apps:
    cred = credentials.Certificate("..\ielts-5bc65-firebase-adminsdk-fbsvc-3abeba7289.json")
    firebase_admin.initialize_app(cred)



@api_view(["POST"])
@permission_classes([AllowAny])
def verify_firebase_token(request):
    """Verify Firebase token, create user, and return JWT"""
    token = request.data.get("token")
    if not token:
        return Response({"error": "No token provided"}, status=400)
    try:
        decoded_token = firebase_auth.verify_id_token(token)
        firebase_uid = decoded_token["uid"]
        email = decoded_token.get("email")
        name = decoded_token.get("name")

        user, created = User.objects.get_or_create(
            firebase_uid=firebase_uid,
            defaults={"email": email, "name": name},
        )

        access, refresh = generate_jwt(user)
        serializer = UserSerializer(user)
        return Response({
            "user": serializer.data,
            "access": access,
            "refresh": refresh,
            "created": created
        })

    except Exception as e:
        return Response({"error": str(e)}, status=400)


@api_view(["POST"])
@permission_classes([AllowAny])
def send_otp(request):
    """Send OTP to phone number"""
    phone = request.data.get("phone")
    if not phone:
        return Response({"error": "Phone number required"}, status=400)

    otp = generate_otp()
    cache.set(f"otp_{phone}", otp, timeout=300)  # OTP valid for 5 minutes

    # TODO: Integrate SMS API here (Twilio/Firebase SMS)
    print(f"Generated OTP for {phone}: {otp}")  # debug only

    return Response({"message": "OTP sent successfully"})


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_otp(request):
    """Verify OTP, create user if needed, return JWT"""
    phone = request.data.get("phone")
    otp = request.data.get("otp")
    if not phone or not otp:
        return Response({"error": "Phone and OTP required"}, status=400)

    cached_otp = cache.get(f"otp_{phone}")
    if cached_otp != otp:
        return Response({"error": "Invalid or expired OTP"}, status=400)

    user, created = User.objects.get_or_create(phone_number=phone)

    access, refresh = generate_jwt(user)
    serializer = UserSerializer(user)
    return Response({
        "user": serializer.data,
        "access": access,
        "refresh": refresh,
        "created": created
    })


@api_view(["GET"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def current_user(request):
    """Return currently logged-in user info"""
    serializer = UserSerializer(request.user)
    return Response({"user": serializer.data})


@api_view(["POST"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def logout_user(request):
    """Log out user"""
    user = request.user
    user.jwt_access = None
    user.jwt_refresh = None
    user.save()
    logout(request)
    return Response({"message": "Logged out successfully"})
