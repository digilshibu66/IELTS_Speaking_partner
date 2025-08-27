# speaking/gemini_service.py
import os
import traceback
import asyncio

from google import genai
from google.genai import types

from .models import SpeakingSession

# ---- Gemini Config ----
MODEL = "models/gemini-2.5-flash-preview-native-audio-dialog"
GOOGLE_API_KEY=os.environ.get("GOOGLE_API_KEY")
# API_KEY = os.environ.get("GOOGLE_API_KEY")
API_KEY = GOOGLE_API_KEY
print(f"Using Gemini API Key: {API_KEY}")
if not API_KEY:
    raise ValueError("GOOGLE_API_KEY not set. Please configure it in your environment.")

client = genai.Client(api_key=API_KEY)


CONFIG = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    media_resolution="MEDIA_RESOLUTION_MEDIUM",
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr")
        )
    ),
    context_window_compression=types.ContextWindowCompressionConfig(
        trigger_tokens=25600,
        sliding_window=types.SlidingWindow(target_tokens=12800),
    ),
)


class DjangoAudioLoop:
    """Handles Gemini live audio session and saving results."""

    def __init__(self, user):
        self.user = user
        self.session = None
        self.collected_text = []
        self.collected_ai_text = []

    async def receive_audio(self):
        """Read model responses, save AI text + audio to DB."""
        while True:
            async for response in self.session.receive():
                if response.text:
                    self.collected_ai_text.append(response.text)
                    yield f"AI: {response.text}\n"
                if response.data:
                    yield response.data  # raw audio bytes

            # Save conversation to DB
            SpeakingSession.objects.create(
                user=self.user,
                question="IELTS Prompt",  # can be dynamic later
                user_text=" ".join(self.collected_text),
                ai_text=" ".join(self.collected_ai_text),
            )
            self.collected_text.clear()
            self.collected_ai_text.clear()

    async def run(self):
        try:
            async with client.aio.live.connect(model=MODEL, config=CONFIG) as session:
                self.session = session
                async for out in self.receive_audio():
                    yield out
        except Exception as e:
            traceback.print_exc()
            yield f"Error: {str(e)}"
