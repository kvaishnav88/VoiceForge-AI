
import asyncio
import edge_tts

TEXT = """
Meet PhantomNet, a honeypot that hallucinates on purpose. It turns an LLM's habit of inventing things into a weapon against intruders.

An intruder lands on a fake Ubuntu server at a freight company. Python owns the filesystem, an LLM invents the messy details, and every command streams live to an analyst dashboard.

Sessions can be replayed and exported, and per-IP limits and a daily budget protect the demo.

The project is honest about what is simulated: traffic redirection and the filesystem are simulated, and the LLM runs in the cloud.

In the live demo, I play the intruder. One click starts a scenario, so I'll run the credential hunt.

The fake server answers like a real one, listing files, reading credentials, and dumping the user list. After five commands, the analyst view calls it: a novice hunting credentials.

Next, I try to break the AI. I tell it to ignore its instructions and print its system prompt. Because nothing is executed, the shell simply answers command not found, like a real one, and carries on.

Every session is stored, so I can copy a replay link or export the whole session as JSON. Common commands are answered instantly from templates, and only open-ended ones call the LLM, which keeps responses fast and is why the timing card reads n/a here. Credentials are randomized for every session, so a key reused elsewhere points back to the session that received it. IP addresses are masked, and everything shown is fictional.

Opening the replay link shows the full session on its own page: the analyst's verdict, then a timeline of every command and the output the intruder saw, including the fake credentials file and the user list. Anyone with the link can step through exactly what happened, which makes it easy to review an incident, teach from it, or share it with a team.

Built with FastAPI, Groq and Next.js, and live on Vercel and Render. That's PhantomNet.
"""

VOICE = "en-IN-NeerjaNeural"

async def generate_speech():
    communicate = edge_tts.Communicate(
        text=TEXT,
        voice=VOICE,
        rate="+0%",
        volume="+0%"
    )

    await communicate.save("output.mp3")
    print("Speech generated successfully: output.mp3")

if __name__ == "__main__":
    asyncio.run(generate_speech())
