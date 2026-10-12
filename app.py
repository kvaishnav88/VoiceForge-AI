
import asyncio
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import edge_tts
import streamlit as st

st.set_page_config(
    page_title="VoiceForge AI",
    page_icon="🎙️",
    layout="wide",
)

# These presets approximate mood through speed and pitch.
# They do not create true emotional acting.
PRESETS = {
    "Neutral": (0, 0),
    "Calm": (-8, -2),
    "Excited": (12, 4),
    "Dramatic": (-10, -4),
    "Serious": (-5, -2),
    "Friendly": (5, 2),
    "Sad": (-12, -3),
    "Energetic": (15, 3),
}

SAMPLE = """Narrator: Welcome to VoiceForge AI.
Maya: I can't believe we finally made it!
Narrator: Suddenly, a strange sound came from the hallway.
Arjun: Stay close. We need to be careful.
Maya: Don't worry. We'll figure this out together."""


# ---------- VOICE ENGINE ----------

async def fetch_voices():
    return await edge_tts.list_voices()


@st.cache_data(ttl=3600, show_spinner=False)
def get_voices():
    voices = asyncio.run(fetch_voices())

    result = []
    for voice in voices:
        name = voice.get("ShortName")
        if name:
            locale = voice.get("Locale", "Unknown")
            gender = voice.get("Gender", "Unknown")
            result.append({
                "name": name,
                "locale": locale,
                "gender": gender,
                "label": f"{name} | {locale} | {gender}",
            })

    return sorted(result, key=lambda x: (x["locale"], x["name"]))


async def speak(text, voice, rate, pitch, output_path):
    communicator = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate,
        pitch=pitch,
    )
    await communicator.save(str(output_path))


# ---------- SCRIPT PROCESSING ----------

def parse_script(script):
    """Read lines formatted as Speaker: dialogue."""
    segments = []

    for line in script.splitlines():
        line = line.strip()

        if not line:
            continue

        match = re.match(
            r"^([A-Za-z0-9 _.-]{1,32}):\s*(.+)$",
            line,
        )

        if match:
            speaker = match.group(1).strip()
            text = match.group(2).strip()
        else:
            speaker = "Narrator"
            text = line

        if text:
            segments.append({
                "speaker": speaker,
                "text": text,
            })

    return segments


def split_long_text(text, limit=1800):
    """Split long speech into smaller chunks."""
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return []

    sentences = re.split(
        r"(?<=[.!?।。！？])\s+",
        text,
    )

    chunks = []
    current = ""

    for sentence in sentences:
        # Handle unusually long individual sentences.
        while len(sentence) > limit:
            if current:
                chunks.append(current)
                current = ""

            chunks.append(sentence[:limit].strip())
            sentence = sentence[limit:].strip()

        if not sentence:
            continue

        candidate = f"{current} {sentence}".strip()

        if len(candidate) > limit and current:
            chunks.append(current)
            current = sentence
        else:
            current = candidate

    if current:
        chunks.append(current)

    return chunks


# ---------- AUDIO ASSEMBLY ----------

def assemble_audio(chunk_paths, folder):
    ffmpeg = shutil.which("ffmpeg")

    if not ffmpeg:
        raise RuntimeError(
            "FFmpeg not found. Install it and restart VS Code."
        )

    concat_file = folder / "concat.txt"
    mp3_path = folder / "narration.mp3"
    wav_path = folder / "narration.wav"

    # The chunk filenames are generated internally.
    concat_file.write_text(
        "".join(
            f"file '{p.as_posix()}'\n"
            for p in chunk_paths
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            ffmpeg, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-vn",
            "-c:a", "libmp3lame",
            "-q:a", "2",
            str(mp3_path),
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "MP3 assembly failed:\n" + result.stderr[-2000:]
        )

    result = subprocess.run(
        [
            ffmpeg, "-y",
            "-i", str(mp3_path),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            str(wav_path),
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "WAV conversion failed:\n" + result.stderr[-2000:]
        )

    return mp3_path.read_bytes(), wav_path.read_bytes()


async def generate_audio(
    segments,
    settings,
    folder,
    progress,
    global_rate_adjust=0,
):
    chunk_paths = []

    jobs = []
    for segment in segments:
        speaker = segment["speaker"]
        config = settings[speaker]

        for chunk in split_long_text(segment["text"]):
            jobs.append((speaker, chunk, config))

    if not jobs:
        raise ValueError("Enter some text first.")


    for index, (speaker, chunk, config) in enumerate(jobs, start=1):
        base_rate, base_pitch = PRESETS[config["preset"]]

        rate = max(
            -50,
            min(
                100,
                base_rate
                + config["rate_adjust"]
                + global_rate_adjust,
            ),
        )

        pitch = max(
            -50,
            min(
                50,
                base_pitch + config["pitch_adjust"],
            ),
        )

        output_path = folder / f"chunk_{index:05d}.mp3"

        await speak(
            text=chunk,
            voice=config["voice"],
            rate=f"{rate:+d}%",
            pitch=f"{pitch:+d}Hz",
            output_path=output_path,
        )

        chunk_paths.append(output_path)

        progress(
            index / len(jobs),
            f"Generating chunk {index}/{len(jobs)} — {speaker}",
        )
    return assemble_audio(chunk_paths, folder)


# ---------- WEB INTERFACE ----------

st.title("🎙️ VoiceForge AI")
st.caption(
    "Multilingual speech | Multi-speaker narration | Long-form audio"
)

st.info(
    "This prototype uses an online neural voice service. "
    "Delivery presets adjust rate and pitch; they do not provide "
    "genuine emotional acting. Automatic translation is not included."
)

with st.sidebar:
    st.header("Engine")
    st.write("Speech: edge-tts")
    st.write("Audio conversion: FFmpeg")
    st.write("API key: Not required")
    st.caption("Internet connection required.")

uploaded = st.file_uploader(
    "Upload a UTF-8 text script (optional)",
    type=["txt"],
)

initial_script = SAMPLE

if uploaded is not None:
    try:
        initial_script = uploaded.getvalue().decode("utf-8-sig")
    except UnicodeDecodeError:
        st.error("Save your text file as UTF-8 and upload it again.")

script = st.text_area(
    "Enter your script",
    value=initial_script,
    height=260,
    help="Use Speaker Name: dialogue to assign different voices.",
)

segments = parse_script(script)
speakers = list(dict.fromkeys(
    item["speaker"] for item in segments
))

# ---------- GLOBAL SPEED AND DURATION ----------

st.subheader("⏱️ Duration and speaking speed")

word_count = len(re.findall(r"\b[\w'-]+\b", script))
estimated_minutes = word_count / 150 if word_count else 0

mode = st.radio(
    "How do you want to control the narration?",
    ["Adjust speed manually", "Set target duration"],
    horizontal=True,
)

global_rate_adjust = 0

if mode == "Adjust speed manually":
    global_rate_adjust = st.slider(
        "Overall speaking speed",
        min_value=-50,
        max_value=100,
        value=0,
        step=5,
        format="%d%%",
        help="Negative values slow speech; positive values speed it up.",
    )

else:
    col1, col2 = st.columns(2)

    with col1:
        target_minutes = st.number_input(
            "Target duration (minutes)",
            min_value=0.1,
            max_value=240.0,
            value=max(0.1, round(estimated_minutes, 1)),
            step=0.5,
        )

    with col2:
        st.metric(
            "Estimated normal-speed duration",
            f"{estimated_minutes:.1f} min",
        )

    if estimated_minutes > 0:
        global_rate_adjust = round(
            (estimated_minutes / target_minutes - 1) * 100
        )

        # Keep within the supported rate-adjustment range.
        global_rate_adjust = max(
            -50,
            min(100, global_rate_adjust),
        )

    st.metric(
        "Calculated speed adjustment",
        f"{global_rate_adjust:+d}%",
    )

    st.caption(
        "The duration is a target. Actual runtime depends on the "
        "selected voices, language, pauses and speaker settings."
    )


c1, c2, c3 = st.columns(3)
c1.metric("Characters", f"{len(script):,}")
c2.metric("Segments", len(segments))
c3.metric("Speakers", len(speakers))

st.markdown("**Example dialogue format**")
st.code(
    "Narrator: It was a quiet evening.\n"
    "Maya: Did you hear that?\n"
    "Arjun: Stay behind me.",
    language="text",
)

# Discover voices supported by the online service.
try:
    voices = get_voices()
except Exception as error:
    st.error(
        f"Unable to retrieve voices: {error}\n\n"
        "Check your internet connection and refresh the app."
    )
    st.stop()

if not voices:
    st.error("No voices were returned by the service.")
    st.stop()

voice_names = [v["name"] for v in voices]
voice_labels = {v["name"]: v["label"] for v in voices}

default_voice = next(
    (v for v in voice_names if v == "en-IN-NeerjaNeural"),
    voice_names[0],
)
second_voice = next(
    (v for v in voice_names if v == "en-IN-PrabhatNeural"),
    default_voice,
)

st.subheader("Configure speakers")
settings = {}

for index, speaker in enumerate(speakers):
    with st.expander(
        f"🗣️ {speaker}",
        expanded=(index == 0),
    ):
        col_a, col_b = st.columns(2)

        preferred = default_voice if index == 0 else second_voice

        with col_a:
            voice = st.selectbox(
                "Voice",
                voice_names,
                index=(
                    voice_names.index(preferred)
                    if preferred in voice_names else 0
                ),
                format_func=lambda v: voice_labels.get(v, v),
                key=f"voice_{index}",
            )

            preset = st.selectbox(
                "Delivery preset",
                list(PRESETS.keys()),
                key=f"preset_{index}",
            )

        with col_b:
            rate_adjust = st.slider(
                "Extra speaking-rate adjustment (%)",
                -20, 20, 0,
                key=f"rate_{index}",
            )

            pitch_adjust = st.slider(
                "Extra pitch adjustment (Hz)",
                -10, 10, 0,
                key=f"pitch_{index}",
            )

        settings[speaker] = {
            "voice": voice,
            "preset": preset,
            "rate_adjust": rate_adjust,
            "pitch_adjust": pitch_adjust,
        }

st.caption(
    "For best results, choose a voice that matches the language "
    "of each speaker's text."
)

if not shutil.which("ffmpeg"):
    st.warning(
        "FFmpeg is missing. Install it and restart VS Code "
        "before generating audio."
    )

if st.button(
    "✨ Generate MP3 + WAV",
    type="primary",
    use_container_width=True,
):
    if not segments:
        st.error("Enter text before generating audio.")

    elif not shutil.which("ffmpeg"):
        st.error("FFmpeg is required. Check `ffmpeg -version`.")

    else:
        progress_bar = st.progress(0.0)
        status = st.empty()


        try:
            with tempfile.TemporaryDirectory(
                prefix="voiceforge_"
            ) as temporary_folder:

                def update_progress(value, message):
                    progress_bar.progress(
                        value,
                        text=message,
                    )
                    status.write(message)

                mp3_data, wav_data = asyncio.run(
                    generate_audio(
                        segments,
                        settings,
                        Path(temporary_folder),
                        update_progress,
                        global_rate_adjust=global_rate_adjust,
                    )
                )

            st.session_state["mp3_data"] = mp3_data
            st.session_state["wav_data"] = wav_data

            st.success("Audio generated successfully!")

        except Exception as error:
            st.error(f"Generation failed: {error}")

if "mp3_data" in st.session_state:
    st.subheader("Preview and download")

    st.audio(
        st.session_state["mp3_data"],
        format="audio/mp3",
    )

    d1, d2 = st.columns(2)

    with d1:
        st.download_button(
            "⬇️ Download MP3",
            data=st.session_state["mp3_data"],
            file_name="voiceforge_narration.mp3",
            mime="audio/mpeg",
            use_container_width=True,
        )

    with d2:
        st.download_button(
            "⬇️ Download WAV",
            data=st.session_state["wav_data"],
            file_name="voiceforge_narration.wav",
            mime="audio/wav",
            use_container_width=True,
        )

with st.expander("Privacy and limitations"):
    st.write(
        "Your script is sent to an online speech service. "
        "Do not submit confidential content. This prototype does "
        "not include voice cloning, automatic translation, or "
        "true emotion-aware synthesis. Review service terms and "
        "voice usage rights before commercial use."
    )
