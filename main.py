import json
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from src.data_processor import from_multiple_pdfs
from src.llm_processor import generate_podcast_script
from src.tts_generator import combine_audio_segments, generate_script_segments


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = PROJECT_ROOT / "source_material"
OUTPUT_DIR = PROJECT_ROOT / "outputs"


def create_openai_client() -> OpenAI:
    """Load the local environment file and create an OpenAI client."""

    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY was not found.")

    return OpenAI(api_key=api_key)


def run_pipeline(
    episode_title: str = "The Future of AI: Catastrophe or Control?",
    pdf_files: list[str | Path] | None = None,
) -> Path:
    """Run the complete podcast-generation pipeline."""

    client = create_openai_client()
    if pdf_files is None:
        pdf_files = sorted(SOURCE_DIR.glob("*.pdf"))

    content = from_multiple_pdfs(pdf_files)

    source_text = content["text"]
    source_details = "\n".join(
        (
            f"- Title: {source['full_title']}\n"
            f"  Authors: {source['author']}\n"
            f"  Year: {source['year']}\n"
            f"  Type: {source['type']}"
        )
        for source in content["sources"]
    )

    podcast_script = generate_podcast_script(
        client=client,
        source_text=source_text,
        episode_title=episode_title,
        source_details=source_details,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    saved_script_path = OUTPUT_DIR / "episode_script.json"
    saved_audio_path = OUTPUT_DIR / "final_episode.mp3"
    saved_sources_path = OUTPUT_DIR / "episode_sources.json"

    # Build everything in a temporary folder first. The existing episode is
    # replaced only after both the new script and new audio are ready.
    with tempfile.TemporaryDirectory(
        prefix="podcast-build-",
        dir=OUTPUT_DIR,
    ) as temporary_folder:
        temporary_folder = Path(temporary_folder)
        temporary_script_path = temporary_folder / "episode_script.json"
        temporary_audio_path = temporary_folder / "final_episode.mp3"
        temporary_sources_path = temporary_folder / "episode_sources.json"

        temporary_script_path.write_text(
            json.dumps(podcast_script, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary_sources_path.write_text(
            json.dumps(content["sources"], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        segment_paths = generate_script_segments(
            client=client,
            script=podcast_script,
            output_dir=temporary_folder / "segments",
        )

        combine_audio_segments(
            segment_paths=segment_paths,
            output_path=temporary_audio_path,
        )

        # Both files exist only after all generation steps above succeed.
        os.replace(temporary_script_path, saved_script_path)
        os.replace(temporary_audio_path, saved_audio_path)
        os.replace(temporary_sources_path, saved_sources_path)

    print(f"Saved script to: {saved_script_path}")
    print(f"Saved source metadata to: {saved_sources_path}")
    print(f"Generated audio segments: {len(segment_paths)}")
    print(f"Saved final audio to: {saved_audio_path}")

    return saved_audio_path


def format_script_for_display(script: dict) -> str:
    """Convert the structured script into readable Markdown."""

    lines = [f"# {script['title']}", ""]

    for segment in script["segments"]:
        lines.append(f"**{segment['speaker']}:** {segment['text']}")
        lines.append("")

    return "\n".join(lines)


def format_source_references(sources: list[dict]) -> str:
    """Format source metadata for display in the Gradio interface."""

    if not sources:
        return "No PDF sources selected."

    lines = []

    for index, source in enumerate(sources, start=1):
        title = source.get("full_title") or source.get("file_name", "Unknown PDF")
        author = source.get("author") or "Author unavailable"
        details = f"{index}. **{author}** — *{title}*"

        if source.get("publication"):
            details += f" — {source['publication']}"

        if source.get("year"):
            details += f" ({source['year']})"

        lines.append(details)

    return "\n\n".join(lines)


def selected_pdf_paths(pdf_files: list[str | Path] | None) -> list[Path]:
    """Use uploaded PDFs, or fall back to the bundled source PDFs."""

    if pdf_files:
        return [Path(pdf_file) for pdf_file in pdf_files]

    return sorted(SOURCE_DIR.glob("*.pdf"))


def preview_sources(pdf_files: list[str | Path] | None) -> str:
    """Read source metadata locally for the UI without making an API call."""

    try:
        content = from_multiple_pdfs(selected_pdf_paths(pdf_files))
    except (FileNotFoundError, ValueError) as error:
        return f"**Source error:** {error}"

    return format_source_references(content["sources"])


def load_existing_episode():
    """Load the already-generated transcript and MP3 for the interface."""

    script_path = OUTPUT_DIR / "episode_script.json"
    audio_path = OUTPUT_DIR / "final_episode.mp3"
    sources_path = OUTPUT_DIR / "episode_sources.json"

    if not script_path.exists():
        raise FileNotFoundError(f"Transcript not found: {script_path}")

    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    script = json.loads(script_path.read_text(encoding="utf-8"))
    transcript = format_script_for_display(script)

    if sources_path.exists():
        sources = json.loads(sources_path.read_text(encoding="utf-8"))
    else:
        sources = from_multiple_pdfs(selected_pdf_paths(None))["sources"]

    return transcript, str(audio_path), format_source_references(sources)


def launch_interface():
    """Create the Podcast Studio interface."""

    import gradio as gr

    def create_episode(pdf_files):
        """Generate a fresh episode, then display the new saved files."""

        # Yield once so the interface can show that processing has started.
        yield (
            "**Status:** Generating a new podcast episode...",
            None,
            "",
            preview_sources(pdf_files),
        )

        try:
            # Always run the complete pipeline. This makes fresh API calls and
            # reflects any changes to the source PDFs or prompt.
            run_pipeline(pdf_files=selected_pdf_paths(pdf_files))
            transcript, audio_path, source_references = load_existing_episode()
        except (FileNotFoundError, ValueError) as error:
            raise gr.Error(str(error)) from error
        except Exception as error:
            print(f"Episode generation failed: {error}")
            raise gr.Error(
                "Could not generate the episode. Check the VS Code terminal "
                "for details."
            ) from error

        yield (
            "**Status:** Episode ready to play.",
            audio_path,
            transcript,
            source_references,
        )

    def load_saved_episode():
        """Load the existing episode without making API calls."""

        try:
            transcript, audio_path, source_references = load_existing_episode()
        except FileNotFoundError as error:
            raise gr.Error(str(error)) from error
        except Exception as error:
            print(f"Saved episode could not be loaded: {error}")
            raise gr.Error(
                "Could not load the saved episode. Check the VS Code terminal "
                "for details."
            ) from error

        return (
            "**Status:** Episode ready to play.",
            audio_path,
            transcript,
            source_references,
        )

    source_references = """
    1. **Rogul, A. (2026).**
       *AI & the End of the World: What the Data Say.*
       Working paper, Bentley University.

    2. **Bareis, J., Ackerl, C., & Heil, R. (2026).**
       *AI going rogue? An integrative narrative review of the tacit assumptions underlying existential AI-risks.*
       **AI and Ethics, 6**, 152. DOI: 10.1007/s43681-025-00928-w

    3. **Olsen, S. G., Reinecke-Tellefsen, C. J., & Østergaard, S. D. (2026).**
       *Potentially harmful consequences of artificial intelligence (AI) chatbot use among patients with mental illness: Early data from a large psychiatric service system.*
       **Acta Psychiatrica Scandinavica, 153**, 301–303. DOI: 10.1111/acps.70068
    """

    # The displayed sources are refreshed when files are uploaded and after
    # a new episode is generated.
    source_references = preview_sources(None)

    css = """
    :root {
        --studio-bg: #090d17;
        --studio-panel: #202736;
        --studio-panel-2: #171d2a;
        --studio-border: #354056;
        --studio-text: #f5f7fb;
        --studio-muted: #b9c2d2;
    }
    body, .gradio-container {
        background: var(--studio-bg) !important;
        color: var(--studio-text) !important;
    }
    .gradio-container { max-width: 100% !important; }
    .gradio-container .block,
    .gradio-container .form,
    .gradio-container .panel,
    .gradio-container .gr-box,
    .gradio-container .gr-group,
    .gradio-container .gradio-group,
    .gradio-container .gradio-accordion,
    .gradio-container fieldset {
        background: var(--studio-panel) !important;
        border-color: var(--studio-border) !important;
    }
    .app-container { max-width: 1100px; margin: auto; padding: 24px 0 48px; }
    .hero {
        padding: 28px;
        border-radius: 16px;
        background: linear-gradient(135deg, #252d3e, #171c2b) !important;
        border: 1px solid var(--studio-border);
    }
    .hero { text-align: center; }
    .hero h1, .hero p { color: var(--studio-text) !important; }
    .hero h1 { font-size: 2.2rem; font-weight: 800; margin: 0 0 10px; }
    .hero p { color: var(--studio-muted) !important; font-size: 1rem; margin: 0; }
    .panel, .gradio-group, .gradio-accordion {
        border-radius: 14px !important;
        border: 1px solid var(--studio-border) !important;
        background: var(--studio-panel) !important;
    }
    .gradio-container label, .gradio-container .block-title,
    .gradio-container .wrap, .gradio-container p,
    .gradio-container h1, .gradio-container h2,
    .gradio-container h3 { color: var(--studio-text) !important; }
    .gradio-container input, .gradio-container textarea {
        background: var(--studio-panel-2) !important;
        color: var(--studio-text) !important;
        border-color: var(--studio-border) !important;
    }
    #source-upload,
    #source-upload > div,
    #source-upload .wrap,
    #source-upload .container,
    #source-upload [data-testid="file-upload"],
    #source-upload .file-dropzone,
    #source-upload .upload-container,
    #source-upload .file-preview {
        background: var(--studio-panel-2) !important;
        color: var(--studio-text) !important;
        border-color: var(--studio-border) !important;
    }
    #source-upload label,
    #source-upload span,
    #source-upload p,
    #source-upload svg {
        color: var(--studio-text) !important;
        fill: var(--studio-text) !important;
    }
    #source-upload button,
    #source-upload [role="button"],
    #source-upload .upload-button,
    #source-upload input[type="file"] {
        background: var(--studio-panel) !important;
        color: var(--studio-text) !important;
        border-color: var(--studio-border) !important;
    }
    #source-upload * {
        border-color: var(--studio-border) !important;
    }
    .gradio-container .audio-container,
    .gradio-container audio {
        background: var(--studio-panel-2) !important;
        color-scheme: dark;
    }
    .gradio-container .prose,
    .gradio-container .markdown,
    .gradio-container .markdown-text {
        color: var(--studio-text) !important;
    }
    .gradio-container .prose h1,
    .gradio-container .prose h2,
    .gradio-container .prose h3,
    .gradio-container .markdown h1,
    .gradio-container .markdown h2,
    .gradio-container .markdown h3 {
        border: 0 !important;
        border-bottom: 0 !important;
        box-shadow: none !important;
        color: var(--studio-text) !important;
    }
    .source-references,
    .source-references * {
        color: var(--studio-text) !important;
        font-size: 0.82rem !important;
        line-height: 1.45 !important;
    }
    .gradio-container .markdown-text a { color: #f472b6 !important; }
    .section-heading h2,
    .gradio-accordion > button,
    .gradio-accordion .label {
        color: var(--studio-text) !important;
        font-size: 1.25rem !important;
        font-weight: 700 !important;
    }
    #podcast-transcript > button,
    #podcast-transcript > button *,
    #podcast-transcript button span {
        color: var(--studio-text) !important;
        font-size: 1.25rem !important;
        font-weight: 700 !important;
    }
    .transcript-content,
    .transcript-content * {
        color: var(--studio-text) !important;
        font-size: 1rem !important;
        line-height: 1.65 !important;
    }
    .transcript-content strong,
    .transcript-content b {
        color: var(--studio-text) !important;
        font-weight: 800 !important;
    }
    .gradio-accordion > button svg {
        color: var(--studio-text) !important;
        fill: var(--studio-text) !important;
        stroke: var(--studio-text) !important;
    }
    #podcast-transcript button svg {
        color: var(--studio-text) !important;
        fill: var(--studio-text) !important;
        stroke: var(--studio-text) !important;
    }
    .play-button {
        font-size: 18px !important;
        font-weight: 700 !important;
        background: linear-gradient(90deg, #7c3aed, #db2777) !important;
        color: white !important;
        border: 0 !important;
    }
    """

    with gr.Blocks(
        title="AI Apocalypse? The Podcast",
        css=css,
        theme=gr.themes.Base(
            primary_hue="pink",
            secondary_hue="purple",
            neutral_hue="slate",
        ),
    ) as demo:
        with gr.Column(elem_classes="app-container"):
            gr.Markdown(
                """
                <div class="hero">
                <h1>AI Apocalypse? The Podcast</h1>
                <p>Listen to a conversational podcast created from the project's source papers.</p>
                </div>
                """
            )

            pdf_upload = gr.File(
                label="Upload PDF sources (optional)",
                file_count="multiple",
                file_types=[".pdf"],
                type="filepath",
                elem_id="source-upload",
            )

            with gr.Row():
                generate_button = gr.Button(
                    "Generate Podcast Episode",
                    variant="primary",
                    elem_classes="play-button",
                )
                load_button = gr.Button(
                    "Load Saved Episode",
                    variant="secondary",
                )

            status_output = gr.Markdown("**Status:** No episode loaded.")

            with gr.Group(elem_classes="panel"):
                gr.Markdown("## Podcast Audio", elem_classes="section-heading")
                audio_output = gr.Audio(
                    show_label=False,
                    type="filepath",
                )

            with gr.Accordion(
                "Podcast Transcript",
                open=True,
                elem_id="podcast-transcript",
            ):
                transcript_output = gr.Markdown(
                    "",
                    elem_classes="transcript-content",
                )

            with gr.Group(elem_classes="panel"):
                gr.Markdown("## Sources", elem_classes="section-heading")
                source_references_output = gr.Markdown(
                    source_references,
                    elem_classes="source-references",
                )

            pdf_upload.change(
                fn=preview_sources,
                inputs=[pdf_upload],
                outputs=[source_references_output],
            )

            generate_button.click(
                fn=create_episode,
                inputs=[pdf_upload],
                outputs=[
                    status_output,
                    audio_output,
                    transcript_output,
                    source_references_output,
                ],
            )

            load_button.click(
                fn=load_saved_episode,
                inputs=[],
                outputs=[
                    status_output,
                    audio_output,
                    transcript_output,
                    source_references_output,
                ],
            )

    return demo


if __name__ == "__main__":
    app = launch_interface()
    app.launch(share=True)
