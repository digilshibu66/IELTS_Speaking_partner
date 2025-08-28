
import asyncio
import json
import csv
import os
import random
import pyaudio
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
        
        # Test state and data storage
        self.test_phase = "not_started"
        self.part2_prep_time = 10
        self.part2_speak_time = 20
        self.is_running = False
        self.conversation_history = []
        self.test_start_time = None
        self.part2_topic = ""
        
        # Create data directory if it doesn't exist
        os.makedirs("ielts_test_data", exist_ok=True)
        
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
                "You are an IELTS speaking test examiner named Alex. You will conduct a mock IELTS speaking test "
                "with three parts. In Part 1, ask 3-4 personal questions about familiar topics like home, "
                "work, studies, hobbies, or interests. In Part 2, give a cue card topic and allow 1 minute "
                "for preparation and 2 minutes for speaking. In Part 3, ask 4-5 follow-up questions "
                "related to the Part 2 topic. Be professional, provide brief feedback at the end, "
                "and keep your responses concise as a real examiner would. Speak clearly and at a moderate pace. "
                "Always address the candidate by their name if provided, or use 'Candidate' otherwise. "
                "Make the test feel natural and conversational."
            )
        )
        
        # Audio streams
        self.input_stream = None
        self.output_stream = None
        
    def add_to_conversation(self, speaker, message, phase=None):
        """Add message to conversation history with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = {
            "timestamp": timestamp,
            "speaker": speaker,
            "message": message,
            "phase": phase or self.test_phase
        }
        self.conversation_history.append(entry)
        self.display_conversation_preview()
        
    def display_conversation_preview(self):
        """Display the latest part of the conversation"""
        print("\n" + "="*60)
        print("CONVERSATION PREVIEW:")
        print("="*60)
        
        # Show last 5-8 messages
        recent_messages = self.conversation_history[-8:] if len(self.conversation_history) > 8 else self.conversation_history
        
        for msg in recent_messages:
            speaker_display = "🤖 EXAMINER" if msg["speaker"] == "examiner" else "🎤 YOU"
            print(f"{msg['timestamp']} [{msg['phase']}] {speaker_display}: {msg['message']}")
        
        print("="*60)
        
    def save_conversation_data(self):
        """Save conversation data to JSON and CSV files"""
        if not self.conversation_history:
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save to JSON
        json_filename = f"ielts_test_data/conversation_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump({
                "test_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "duration": str(datetime.now() - self.test_start_time) if self.test_start_time else "N/A",
                "part2_topic": self.part2_topic,
                "conversation": self.conversation_history
            }, f, indent=2, ensure_ascii=False)
        
        # Save to CSV
        csv_filename = f"ielts_test_data/conversation_{timestamp}.csv"
        with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Timestamp', 'Phase', 'Speaker', 'Message'])
            for msg in self.conversation_history:
                writer.writerow([msg['timestamp'], msg['phase'], msg['speaker'], msg['message']])
        
        print(f"\n💾 Conversation saved to: {json_filename} and {csv_filename}")
        
    def extract_questions(self):
        """Extract questions from conversation history"""
        questions = []
        for msg in self.conversation_history:
            if msg['speaker'] == 'examiner' and ('?' in msg['message'] or msg['message'].lower().startswith(('tell me', 'describe', 'talk about', 'what', 'how', 'why'))):
                questions.append({
                    'phase': msg['phase'],
                    'question': msg['message'],
                    'timestamp': msg['timestamp']
                })
        return questions
        
    def show_test_summary(self):
        """Display test summary with questions and statistics"""
        questions = self.extract_questions()
        
        print("\n" + "="*60)
        print("📊 TEST SUMMARY")
        print("="*60)
        print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Duration: {str(datetime.now() - self.test_start_time) if self.test_start_time else 'N/A'}")
        print(f"Part 2 Topic: {self.part2_topic}")
        
        print(f"\n📝 Questions Asked: {len(questions)}")
        for i, q in enumerate(questions, 1):
            print(f"{i}. [{q['phase']}] {q['question']}")
            
        print(f"\n💬 Total Exchanges: {len(self.conversation_history)}")
        examiner_msgs = sum(1 for msg in self.conversation_history if msg['speaker'] == 'examiner')
        candidate_msgs = sum(1 for msg in self.conversation_history if msg['speaker'] == 'candidate')
        print(f"   Examiner: {examiner_msgs} messages")
        print(f"   You: {candidate_msgs} messages")
        print("="*60)
        
    async def initialize_audio(self):
        """Initialize audio streams with error handling"""
        try:
            # Get default input device
            mic_info = self.pya.get_default_input_device_info()
            print(f"🎤 Using input device: {mic_info['name']}")
            
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
            print(f"❌ Audio initialization error: {e}")
            return False
    
    async def listen_audio(self):
        """Capture audio from microphone"""
        print("🔊 Audio listening started...")
        while self.is_running:
            try:
                # Read audio data
                data = await asyncio.to_thread(self.input_stream.read, CHUNK_SIZE, exception_on_overflow=False)
                if self.session:
                    await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})
                    # Add user speaking indicator to conversation
                    if random.random() < 0.1:  # Occasionally show user is speaking
                        self.add_to_conversation("candidate", "[Speaking...]", self.test_phase)
                await asyncio.sleep(0.01)
            except Exception as e:
                if self.is_running:
                    print(f"❌ Audio capture error: {e}")
                await asyncio.sleep(0.1)
    
    async def receive_audio(self):
        """Receive audio responses from Gemini"""
        print("📡 Audio reception started...")
        try:
            while self.is_running and self.session:
                turn = self.session.receive()
                async for response in turn:
                    if data := response.data:
                        await self.audio_in_queue.put(data)
                    if text := response.text:
                        print(f"🤖 Examiner: {text}")
                        self.add_to_conversation("examiner", text, self.test_phase)
                        
                        # Extract Part 2 topic if mentioned
                        if "part 2" in text.lower() and "describe" in text.lower():
                            self.part2_topic = text
        except Exception as e:
            if self.is_running:
                print(f"❌ Audio reception error: {e}")
    
    async def play_audio(self):
        """Play received audio responses"""
        print("🔊 Audio playback started...")
        while self.is_running:
            try:
                bytestream = await self.audio_in_queue.get()
                await asyncio.to_thread(self.output_stream.write, bytestream)
            except Exception as e:
                if self.is_running:
                    print(f"❌ Audio playback error: {e}")
                await asyncio.sleep(0.1)
    
    async def start_test(self):
        """Start the IELTS speaking test"""
        print("🎯 Starting IELTS Speaking Mock Test...")
        print("=" * 60)
        
        # Get candidate name for personalization
        candidate_name = input("Enter your name (or press Enter to skip): ").strip()
        if candidate_name:
            self.config.system_instruction += f" The candidate's name is {candidate_name}."
        
        print("The examiner will now begin the test. Please wait for the questions.")
        self.test_start_time = datetime.now()
        
        # Initialize audio
        if not await self.initialize_audio():
            print("❌ Failed to initialize audio. Please check your microphone and speakers.")
            return
        
        self.is_running = True
        
        try:
            # Connect to Gemini
            async with self.client.aio.live.connect(
                model="models/gemini-2.0-flash-live-001", 
                config=self.config
            ) as session:
                
                self.session = session
                print("✅ Successfully connected to Gemini API")
                self.add_to_conversation("system", "Test session started", "initialization")
                
                # Start background tasks
                listen_task = asyncio.create_task(self.listen_audio())
                receive_task = asyncio.create_task(self.receive_audio())
                play_task = asyncio.create_task(self.play_audio())
                
                # Run the test sequence
                try:
                    await self.run_test_sequence()
                except Exception as e:
                    print(f"❌ Test sequence error: {e}")
                    self.add_to_conversation("system", f"Test error: {e}", "error")
                
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
            print("❌ Connection to Gemini API timed out. Please check your internet connection.")
        except GoogleAPIError as e:
            print(f"❌ Google API error: {e}. Please check your API key and quota.")
        except Exception as e:
            print(f"❌ Connection error: {e}")
        finally:
            self.is_running = False
            self.add_to_conversation("system", "Test session ended", "completion")
            self.save_conversation_data()
            self.show_test_summary()
            await self.cleanup()
    
    async def run_test_sequence(self):
        """Run the complete IELTS test sequence"""
        # Wait a moment for everything to initialize
        await asyncio.sleep(2)
        
        try:
            # Let the AI examiner start the test automatically
            start_prompt = "Please begin the IELTS speaking test with Part 1 questions. Start by introducing yourself as the examiner."
            await self.session.send(input=start_prompt, end_of_turn=True)
            
            # Part 1: Introduction and Interview
            self.test_phase = "part1"
            print("\n📋 Part 1: Introduction and Interview")
            print("-" * 50)
            print("Answer the examiner's questions about familiar topics.")
            self.add_to_conversation("system", "Part 1 started", "part1")
            
            # Wait for Part 1 to complete (realistic timing)
            await asyncio.sleep(20)  # 3 minutes
            
            # Transition to Part 2
            self.test_phase = "transition"
            transition_prompt = "Please now move to Part 2 of the test. Provide a cue card topic for the long turn."
            await self.session.send(input=transition_prompt, end_of_turn=True)
            await asyncio.sleep(5)
            
            # Part 2: Long Turn
            self.test_phase = "part2"
            print("\n📋 Part 2: Long Turn")
            print("-" * 50)
            print("You will receive a topic and have 1 minute to prepare, then 2 minutes to speak.")
            self.add_to_conversation("system", "Part 2 started - preparation time", "part2")
            
            # Simulate preparation time
            for i in range(self.part2_prep_time, 0, -10):
                if i > 0:
                    print(f"⏰ Preparation time: {i} seconds remaining")
                    await asyncio.sleep(10)
            
            print("🎤 Start speaking now (2 minutes)")
            self.add_to_conversation("system", "Part 2 - speaking time", "part2")
            await asyncio.sleep(self.part2_speak_time)
            
            # Transition to Part 3
            self.test_phase = "transition"
            transition_prompt = "Please now move to Part 3 with follow-up questions about the Part 2 topic."
            await self.session.send(input=transition_prompt, end_of_turn=True)
            await asyncio.sleep(5)
            
            # Part 3: Discussion
            self.test_phase = "part3"
            print("\n📋 Part 3: Discussion")
            print("-" * 50)
            print("Answer the examiner's follow-up questions about the Part 2 topic.")
            self.add_to_conversation("system", "Part 3 started", "part3")
            
            # Wait for Part 3 to complete
            await asyncio.sleep(20)  # 4 minutes
            
            # End of test and request feedback
            self.test_phase = "feedback"
            feedback_request = "That concludes the speaking test. Please provide brief feedback on my performance, focusing on fluency, vocabulary, grammar, and pronunciation. Also suggest areas for improvement."
            await self.session.send(input=feedback_request, end_of_turn=True)
            await asyncio.sleep(45)  # Wait for feedback
            
            print("\n✅ Test completed! Thank you for using the IELTS Speaking Mock Test.")
            self.add_to_conversation("system", "Test completed successfully", "completion")
            
        except Exception as e:
            print(f"❌ Error in test sequence: {e}")
            self.add_to_conversation("system", f"Test sequence error: {e}", "error")
            raise
    
    async def cleanup(self):
        """Clean up resources"""
        print("🧹 Cleaning up resources...")
        
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
        print("\n⏹️ Test interrupted by user.")
        partner.add_to_conversation("system", "Test interrupted by user", "interrupted")
        partner.save_conversation_data()
        partner.show_test_summary()
    except Exception as e:
        print(f"❌ An error occurred: {e}")
        partner.add_to_conversation("system", f"Unexpected error: {e}", "error")
        partner.save_conversation_data()
    finally:
        print("🏁 Program ended.")


# # For testing the script directly
# if __name__ == "__main__":
#     print("🎓 IELTS Speaking Test Partner")
#     print("=" * 40)
#     print("This mock test will simulate a real IELTS speaking test")
#     print("with three parts: Introduction, Long Turn, and Discussion")
#     print("\n📁 Your conversation will be saved in the 'ielts_test_data' folder")
#     print("⏰ Total test time: Approximately 10-12 minutes")
#     print("=" * 40)
    
#     input("Press Enter to begin the test...")
    
#     asyncio.run(run_ielts_mock_test())