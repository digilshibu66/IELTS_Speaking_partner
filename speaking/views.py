from django.http import StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed

from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import authentication_classes, permission_classes
from .gemini_service import DjangoAudioLoop

def live_speaking_view(request):
    # Manually validate JWT from cookie
    token = request.COOKIES.get("access")
    if not token:
        return StreamingHttpResponse("Unauthorized\n", status=401)

    auth = JWTAuthentication()
    try:
        validated_token = auth.get_validated_token(token)
        user = auth.get_user(validated_token)
    except AuthenticationFailed:
        return StreamingHttpResponse("Unauthorized\n", status=401)

    loop = DjangoAudioLoop(user)

    async def event_stream_async():
        async for chunk in loop.run():
            if isinstance(chunk, bytes):
                yield f"data: {chunk.hex()}\n\n".encode()
            else:
                yield f"data: {chunk}\n\n".encode()

    async def async_to_bytes():
        async for item in event_stream_async():
            yield item

    response = StreamingHttpResponse(
        async_to_bytes(),
        content_type="text/event-stream",
        status=200
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'  # if using nginx
    return response
