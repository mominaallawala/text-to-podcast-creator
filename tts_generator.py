from pydub import AudioSegment
#import re to help python recognize sentence endings.
import re 
from pathlib import Path
from openai import OpenAI

from src.hosts import HOSTS

#splittng text into word-based chunks below the speech API limit and also not cuttng speaker in the middle. allow complete sentences

def split_text_into_chunks(
    text: str,
    max_chars: int = 4000,
) -> list[str]:
    """
    Split text at sentence boundaries when possible.
    """

    if not text.strip():
        raise ValueError("Text cannot be empty.")

    cleaned_text = " ".join(text.split())
    sentences = re.split(r"(?<=[.!?])\s+", cleaned_text)

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        candidate = f"{current_chunk} {sentence}".strip()

        if len(candidate) <= max_chars:
            current_chunk = candidate
        else:
            if current_chunk:
                chunks.append(current_chunk)

            current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def generate_speech(
    client: OpenAI,
    text: str,
    output_path: str | Path,
    voice: str = "coral",
) -> Path:
    """
    Convert text into an MP3 audio file.
    """

    if not text.strip():
        raise ValueError("Text cannot be empty.")

    if len(text) > 4096:
        raise ValueError(
            "Text is longer than the speech API limit. "
            "Chunking will be added next."
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with client.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts",
        voice=voice,
        input=text,
        instructions="Speak clearly in a warm, conversational podcast style.",
        response_format="mp3",
    ) as response:
        response.stream_to_file(output_path)

    return output_path

def generate_script_segments(
    client: OpenAI,
    script: dict,
    output_dir: str | Path = "outputs/segments",
) -> list[Path]:
    """
    Generate one MP3 file for each podcast segment.
    """

    if "segments" not in script:
        raise ValueError("Script is missing the 'segments' field.")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    segment_paths = []

    for index, segment in enumerate(script["segments"], start=1):
        speaker = segment["speaker"]
        text = segment["text"]

        if speaker not in HOSTS:
            raise ValueError(f"Unknown speaker: {speaker}")
        
# Split long segments before sending them to the TTS API.
        chunks = split_text_into_chunks(text)

        for chunk_index, chunk_text in enumerate(chunks, start=1):
            output_path = (
                output_dir
                / f"segment_{index:03}_{speaker}_part_{chunk_index:02}.mp3"
            )

            generate_speech(
                client=client,
                text=chunk_text,
                output_path=output_path,
                voice=HOSTS[speaker]["voice"],
            )

            segment_paths.append(output_path)

       
    return segment_paths

##This function: reads the Ana and Rui MP3 files in order; joins them together;creates one final MP3; preserve the conversation sequence.

def combine_audio_segments(
    segment_paths: list[str | Path],
    output_path: str | Path,
) -> Path:
    """
    Combine MP3 segment files into one MP3 file.
    """

    if not segment_paths:
        raise ValueError("No audio segments were provided.")

    combined_audio = AudioSegment.empty()

    for segment_path in segment_paths:
        segment_path = Path(segment_path)

        if not segment_path.exists():
            raise FileNotFoundError(
                f"Audio segment not found: {segment_path}"
            )

        combined_audio += AudioSegment.from_file(segment_path)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    combined_audio.export(output_path, format="mp3")

    return output_path
