"""
IELTS Speaking Test Partner using Google Gemini API (Audio Only)
"""

import asyncio
import base64
import io
import random
import time
import pyaudio

from google import genai
from google.genai import types

# Audio configuration
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

# API Key embedded in the code
GEMINI_API_KEY = "AIzaSyD7KdjfbbNdsJzpZ5L3vIm6bvn27qqiiXU"

class IELTSSpeakingPartner:
    def __init__(self):
        self.client = genai.Client(
            http_options={"api_version": "v1beta"},
            api_key=GEMINI_API_KEY,
        )
        
        self.pya = pyaudio.PyAudio()
        self.session = None
        self.audio_in_queue = asyncio.Queue()
        self.out_queue = asyncio.Queue(maxsize=5)
        
        # Test state
        self.test_phase = "not_started"
        self.part2_prep_time = 60  # 1 minute preparation time
        self.part2_speak_time = 120  # 2 minutes speaking time
        
        # Configure Gemini for IELTS context
        self.config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            media_resolution="MEDIA_RESOLUTION_MEDIUM",
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Charon")
                )
            ),
            context_window_compression=types.ContextWindowCompressionConfig(
                trigger_tokens=25600,
                sliding_window=types.SlidingWindow(target_tokens=12800),
            ),
            system_instruction=(
                "You are an IELTS speaking test examiner. You will conduct a mock IELTS speaking test "
                "with three parts. In Part 1, ask 3-4 personal questions about familiar topics like home, "
                "work, studies, hobbies, or interests. In Part 2, give a cue card topic and allow 1 minute "
                "for preparation and 2 minutes for speaking. In Part 3, ask 4-5 follow-up questions "
                "related to the Part 2 topic. Be professional, provide brief feedback at the end, "
                "and keep your responses concise as a real examiner would. Generate appropriate questions "
                "for each part automatically without needing predefined lists."
            )
        )
    
    async def listen_audio(self):
        """Capture audio from microphone"""
        mic_info = self.pya.get_default_input_device_info()
        self.audio_stream = await asyncio.to_thread(
            self.pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=SEND_SAMPLE_RATE,
            input=True,
            input_device_index=mic_info["index"],
            frames_per_buffer=CHUNK_SIZE,
        )
        
        kwargs = {"exception_on_overflow": False} if __debug__ else {}
        while True:
            data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
            await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})
    
    async def receive_audio(self):
        """Receive audio responses from Gemini"""
        while True:
            turn = self.session.receive()
            async for response in turn:
                if data := response.data:
                    self.audio_in_queue.put_nowait(data)
                if text := response.text:
                    print(f"Examiner: {text}")
            
            # Clear audio queue if interrupted
            while not self.audio_in_queue.empty():
                self.audio_in_queue.get_nowait()
    
    async def play_audio(self):
        """Play received audio responses"""
        stream = await asyncio.to_thread(
            self.pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
        )
        while True:
            bytestream = await self.audio_in_queue.get()
            await asyncio.to_thread(stream.write, bytestream)
    
    async def start_test(self):
        """Start the IELTS speaking test"""
        print("Starting IELTS Speaking Mock Test...")
        print("=" * 50)
        print("The examiner will now begin the test. Please wait for the questions.")
        
        async with (
            self.client.aio.live.connect(model="models/gemini-2.5-flash-preview-native-audio-dialog", 
                                        config=self.config) as session,
            asyncio.TaskGroup() as tg,
        ):
            self.session = session
            
            # Start background tasks
            tg.create_task(self.listen_audio())
            tg.create_task(self.receive_audio())
            tg.create_task(self.play_audio())
            
            # Begin the test
            await self.run_test_sequence()
    
    async def run_test_sequence(self):
        """Run the complete IELTS test sequence"""
        # Introduction
        await asyncio.sleep(2)
        
        # Let the AI examiner start the test automatically
        start_prompt = "Please begin the IELTS speaking test with Part 1 questions."
        await self.session.send(input=start_prompt, end_of_turn=True)
        await asyncio.sleep(10)  # Wait for examiner introduction
        
        # Part 1: Let the AI ask questions automatically
        self.test_phase = "part1"
        print("\nPart 1: Introduction and Interview")
        print("-" * 40)
        print("Answer the examiner's questions about familiar topics.")
        
        # Wait for Part 1 to complete (approximately 4-5 minutes)
        await asyncio.sleep(240)
        
        # Transition to Part 2
        transition_prompt = "Please now move to Part 2 of the test with a cue card topic."
        await self.session.send(input=transition_prompt, end_of_turn=True)
        await asyncio.sleep(5)
        
        # Part 2: Long Turn
        self.test_phase = "part2"
        print("\nPart 2: Long Turn")
        print("-" * 40)
        print("You will receive a topic and have 1 minute to prepare, then 2 minutes to speak.")
        
        # Wait for preparation and speaking time
        await asyncio.sleep(self.part2_prep_time + self.part2_speak_time + 10)
        
        # Transition to Part 3
        transition_prompt = "Please now move to Part 3 with follow-up questions."
        await self.session.send(input=transition_prompt, end_of_turn=True)
        await asyncio.sleep(5)
        
        # Part 3: Discussion
        self.test_phase = "part3"
        print("\nPart 3: Discussion")
        print("-" * 40)
        print("Answer the examiner's follow-up questions about the Part 2 topic.")
        
        # Wait for Part 3 to complete (approximately 4-5 minutes)
        await asyncio.sleep(240)
        
        # End of test and request feedback
        self.test_phase = "completed"
        feedback_request = "That concludes the speaking test. Please provide brief feedback on my performance, focusing on fluency, vocabulary, grammar, and pronunciation."
        await self.session.send(input=feedback_request, end_of_turn=True)
        await asyncio.sleep(15)
        
        print("\nTest completed! Thank you for using the IELTS Speaking Mock Test.")


# Function to be called from outside the file
async def run_ielts_mock_test():
    """Run the IELTS mock test - call this function from other files"""
    partner = IELTSSpeakingPartner()
    
    try:
        await partner.start_test()
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        print("Cleaning up resources...")