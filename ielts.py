"""
IELTS Speaking Test Partner using Google Gemini API (Audio Only)
Fixed connection handling
"""

import asyncio
import base64
import io
import random
import time
import pyaudio
import wave
import threading
from datetime import datetime

from google import genai
from google.genai import types
from google.api_core.exceptions import GoogleAPIError

# Audio configuration
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

# API Key - consider using environment variables for security
GEMINI_API_KEY = "AIzaSyD7KdjfbbNdsJzpZ5L3vIm6bvn27qqiiXU"

class IELTSSpeakingPartner:
    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        
        self.pya = pyaudio.PyAudio()
        self.session = None
        self.audio_in_queue = asyncio.Queue()
        self.out_queue = asyncio.Queue(maxsize=5)
        
        # Test state
        self.test_phase = "not_started"
        self.part2_prep_time = 60
        self.part2_speak_time = 120
        self.is_running = False
        
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
                "for each part automatically without needing predefined lists. Speak clearly and at a moderate pace."
            )
        )
        
        # Audio streams
        self.input_stream = None
        self.output_stream = None
        
    async def initialize_audio(self):
        """Initialize audio streams with error handling"""
        try:
            # Get default input device
            mic_info = self.pya.get_default_input_device_info()
            print(f"Using input device: {mic_info['name']}")
            
            # Open input stream
            self.input_stream = await asyncio.to_thread(
                self.pya.open,
                format=FORMAT,
                channels=CHANNELS,
                rate=SEND_SAMPLE_RATE,
                input=True,
                input_device_index=mic_info["index"],
                frames_per_buffer=CHUNK_SIZE,
            )
            
            # Open output stream
            self.output_stream = await asyncio.to_thread(
                self.pya.open,
                format=FORMAT,
                channels=CHANNELS,
                rate=RECEIVE_SAMPLE_RATE,
                output=True,
            )
            
            return True
        except Exception as e:
            print(f"Audio initialization error: {e}")
            return False
    
    async def listen_audio(self):
        """Capture audio from microphone"""
        print("Audio listening started...")
        while self.is_running:
            try:
                # Read audio data
                data = await asyncio.to_thread(self.input_stream.read, CHUNK_SIZE, exception_on_overflow=False)
                if self.session:
                    await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})
                await asyncio.sleep(0.01)
            except Exception as e:
                if self.is_running:  # Only log if we're still running
                    print(f"Audio capture error: {e}")
                await asyncio.sleep(0.1)
    
    async def receive_audio(self):
        """Receive audio responses from Gemini"""
        print("Audio reception started...")
        try:
            while self.is_running and self.session:
                turn = self.session.receive()
                async for response in turn:
                    if data := response.data:
                        await self.audio_in_queue.put(data)
                    if text := response.text:
                        print(f"Examiner: {text}")
        except Exception as e:
            if self.is_running:  # Only log if we're still running
                print(f"Audio reception error: {e}")
    
    async def play_audio(self):
        """Play received audio responses"""
        print("Audio playback started...")
        while self.is_running:
            try:
                bytestream = await self.audio_in_queue.get()
                await asyncio.to_thread(self.output_stream.write, bytestream)
            except Exception as e:
                if self.is_running:  # Only log if we're still running
                    print(f"Audio playback error: {e}")
                await asyncio.sleep(0.1)
    
    async def start_test(self):
        """Start the IELTS speaking test"""
        print("Starting IELTS Speaking Mock Test...")
        print("=" * 50)
        print("The examiner will now begin the test. Please wait for the questions.")
        
        # Initialize audio
        if not await self.initialize_audio():
            print("Failed to initialize audio. Please check your microphone and speakers.")
            return
        
        self.is_running = True
        
        try:
            # Connect to Gemini - this returns a context manager, not a coroutine
            async with self.client.aio.live.connect(
                model="models/gemini-2.5-flash-preview-native-audio-dialog", 
                config=self.config
            ) as session:
                
                self.session = session
                print("✅ Successfully connected to Gemini API")
                
                # Start background tasks
                listen_task = asyncio.create_task(self.listen_audio())
                receive_task = asyncio.create_task(self.receive_audio())
                play_task = asyncio.create_task(self.play_audio())
                
                # Run the test sequence
                try:
                    await self.run_test_sequence()
                except Exception as e:
                    print(f"Test sequence error: {e}")
                
                # Cancel background tasks
                listen_task.cancel()
                receive_task.cancel()
                play_task.cancel()
                
                # Wait for tasks to finish
                try:
                    await asyncio.gather(listen_task, receive_task, play_task, return_exceptions=True)
                except:
                    pass
                
        except asyncio.TimeoutError:
            print("Connection to Gemini API timed out. Please check your internet connection.")
        except GoogleAPIError as e:
            print(f"Google API error: {e}. Please check your API key and quota.")
        except Exception as e:
            print(f"Connection error: {e}")
        finally:
            self.is_running = False
            await self.cleanup()
    
    async def run_test_sequence(self):
        """Run the complete IELTS test sequence"""
        # Wait a moment for everything to initialize
        await asyncio.sleep(2)
        
        try:
            # Let the AI examiner start the test automatically
            start_prompt = "Please begin the IELTS speaking test with Part 1 questions."
            await self.session.send(input=start_prompt, end_of_turn=True)
            
            # Part 1: Introduction and Interview
            self.test_phase = "part1"
            print("\nPart 1: Introduction and Interview")
            print("-" * 40)
            print("Answer the examiner's questions about familiar topics.")
            
            # Wait for Part 1 to complete
            await asyncio.sleep(20)  # 1 minute for testing
            
            # Transition to Part 2
            transition_prompt = "Please now move to Part 2 of the test with a cue card topic."
            await self.session.send(input=transition_prompt, end_of_turn=True)
            await asyncio.sleep(10)
            
            # Part 2: Long Turn
            self.test_phase = "part2"
            print("\nPart 2: Long Turn")
            print("-" * 40)
            print("You will receive a topic and have 1 minute to prepare, then 2 minutes to speak.")
            
            # Wait for preparation and speaking time
            # await asyncio.sleep(self.part2_prep_time + self.part2_speak_time + 10)
            await asyncio.sleep(10)
            # Transition to Part 3
            transition_prompt = "Please now move to Part 3 with follow-up questions."
            await self.session.send(input=transition_prompt, end_of_turn=True)
            await asyncio.sleep(10)
            
            # Part 3: Discussion
            self.test_phase = "part3"
            print("\nPart 3: Discussion")
            print("-" * 40)
            print("Answer the examiner's follow-up questions about the Part 2 topic.")
            
            # Wait for Part 3 to complete
            await asyncio.sleep(20)  # 2 minutes for testing
            
            # End of test and request feedback
            self.test_phase = "completed"
            feedback_request = "That concludes the speaking test. Please provide brief feedback on my performance, focusing on fluency, vocabulary, grammar, and pronunciation."
            await self.session.send(input=feedback_request, end_of_turn=True)
            await asyncio.sleep(30)  # Wait for feedback
            
            print("\nTest completed! Thank you for using the IELTS Speaking Mock Test.")
            
        except Exception as e:
            print(f"Error in test sequence: {e}")
            raise
    
    async def cleanup(self):
        """Clean up resources"""
        print("Cleaning up resources...")
        
        if self.input_stream:
            try:
                self.input_stream.stop_stream()
                self.input_stream.close()
            except:
                pass
        
        if self.output_stream:
            try:
                self.output_stream.stop_stream()
                self.output_stream.close()
            except:
                pass
        
        try:
            self.pya.terminate()
        except:
            pass


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
        print("Program ended.")


# For testing the script directly
# if __name__ == "__main__":
#     print("IELTS Speaking Test Partner")
#     print("=" * 30)
#     input("Press Enter to begin the test...")
    
#     asyncio.run(run_ielts_mock_test())