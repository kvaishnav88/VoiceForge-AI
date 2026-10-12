
import asyncio
import edge_tts
from pathlib import Path


async def generate_speech(
    text: str,
    voice: str,
    output_file: str,
    rate: str = "+0%",
    pitch: str = "+0Hz",
):
    """Convert text into speech and save it as an audio file."""

    if not text.strip():
        raise ValueError("Text cannot be empty.")

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tts = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate,
        pitch=pitch,
    )

    await tts.save(str(output_path))
    return str(output_path)


def text_to_speech(
    text: str,
    voice: str,
    output_file: str,
    rate: str = "+0%",
    pitch: str = "+0Hz",
):
    """Synchronous interface for the speech engine."""

    return asyncio.run(
        generate_speech(
            text=text,
            voice=voice,
            output_file=output_file,
            rate=rate,
            pitch=pitch,
        )
    )


if __name__ == "__main__":
    result = text_to_speech(
        text="Hello! Welcome to my Text-to-Speech AI Agent.",
        voice="en-IN-NeerjaNeural",
        output_file="outputs/test.mp3",
    )
    print(f"Audio saved to: {result}")
