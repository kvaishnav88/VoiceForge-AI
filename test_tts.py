import asyncio
import edge_tts

TEXT = "Hello, this is my first AI generated voice."
VOICE = "en-IN-NeerjaNeural"

async def main():
    communicate = edge_tts.Communicate(TEXT, VOICE)
    await communicate.save("test.mp3")
    print("Saved test.mp3")

asyncio.run(main())
