"""
Main script to run the IELTS Speaking Mock Test
"""

import asyncio

from ielts import run_ielts_mock_test


async def main():
    print("IELTS Speaking Mock Test Partner")
    print("=" * 30)
    print("This will simulate a complete IELTS speaking test with an AI examiner.")
    print("The test includes:")
    print("- Part 1: Introduction and interview (4-5 questions)")
    print("- Part 2: Long turn with cue card (1 min prep + 2 min speaking)")
    print("- Part 3: Discussion (4-5 follow-up questions)")
    print("- Final feedback on your performance")
    print("\nPress Ctrl+C at any time to exit the test.")
    
    input("\nPress Enter to begin the test...")
    
    await run_ielts_mock_test()

if __name__ == "__main__":
    asyncio.run(main())