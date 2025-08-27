from django.db import models
from django.conf import settings

class SpeakingSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="speaking_sessions"
    )
    question = models.TextField()  # Question asked (IELTS speaking prompt)
    user_audio = models.FileField(upload_to="speaking/user_audio/", blank=True, null=True)  # Raw audio file
    user_text = models.TextField(blank=True, null=True)  # Transcribed text of user speech
    ai_text = models.TextField(blank=True, null=True)  # Gemini-generated text
    ai_audio = models.FileField(upload_to="speaking/ai_audio/", blank=True, null=True)  # Gemini reply audio
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Speaking session ({self.user.email}) - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
