# Podcast Studio

A small Python pipeline that turns UTF-8 source material into a podcast script and an MP3 using the OpenAI API.

🎙️ AI Apocalypse? — Podcast Studio

## About

_AI Apocalypse?_ is a short podcast that looks at the big fears around artificial intelligence: job loss, misinformation, loss of control, the "superintelligence" scenario.

It asks how much of each fear is real and how much is hype. The question mark is deliberate: we're not predicting the end of the world. We're testing the claims.

## Format

- **Length:** ~5–10 min per episode
- **Style:** Conversational, with two hosts. Each episode takes one fear, lays out the arguments on each side, and ends with a takeaway.

- **Audience:** AI Curious non-experts, professionals wondering how AI will affect their work

## Episode ideas

1. Will AI take my job?
2. Deepfakes & the end of trust
3. Who's in control: alignment, explained simply
4. Doom vs. hype: separating signal from noise

## How we built it

We used AI tools across the whole workflow: research, scripting, voice generation, audio editing and cover art.

## Team

- Carolina Uchoa
- Momina Allawala
- Tamara Kisters

## Project structure

```text
podcast-studio/
├── src/
│   ├── data_processor.py
│   ├── llm_processor.py
│   ├── tts_generator.py
│   └── main.py
├── outputs/
├── requirements.txt
├── README.md
├── .env                 # local only; never commit
└── .gitignore
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
export OPENAI_API_KEY="your-api-key"
```
## Installation

Install the Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Run

Put source material in a text file and run:

```bash
python src/main.py input.txt --output outputs/episode.mp3
```

Generated audio is kept in `outputs/`, which is ignored by Git except for its `.gitkeep` placeholder.

### Install FFmpeg for audio generation

Podcast Studio uses `pydub` and FFmpeg to combine Ana and Rui’s audio clips
into one MP3.

1. Install the Python dependencies from the project folder:

   ```bash
   pip install -r requirements.txt
   ```

2. Install FFmpeg separately. On Windows, extract the FFmpeg download and
   add the `bin` folder that contains `ffmpeg.exe` to your Windows `PATH`.
3. Reopen the VS Code terminal and check that FFmpeg is available:

   ```bash
   ffmpeg -version
   ```

   If the terminal shows version information, you’re ready to generate audio.
   The finished episode is saved to `outputs/final_episode.mp3`.

## Sources


The podcast episode is generated from three PDF papers stored in
`source_material/`. The hosts are instructed to credit authors and
publications aloud when discussing the papers.

| File | Authors | Publication | Type |
|---|---|---|---|
| AI and the End of the World.pdf | Alexander Rogul | Working paper, Bentley University, 2026 | Working paper |
| AI going rogue.pdf | Jascha Bareis, Clemens Ackerl, Reinhard Heil | AI and Ethics, 2026 | Peer-reviewed narrative review |
| Potentially Harmful Consequences of AI.pdf | Sidse Godske Olsen, Christian Jon Reinecke-Tellefsen, Søren Dinesen Østergaard | Acta Psychiatrica Scandinavica, 2026 | Peer-reviewed research letter |

### Full references

1. Rogul, A. (2026). *AI & the End of the World: What the Data Say*. Working paper, Bentley University.

2. Bareis, J., Ackerl, C., & Heil, R. (2026). *AI going rogue? An integrative narrative review of the tacit assumptions underlying existential AI-risks*. *AI and Ethics, 6*, 152. https://doi.org/10.1007/s43681-025-00928-w

3. Olsen, S. G., Reinecke-Tellefsen, C. J., & Østergaard, S. D. (2026). *Potentially harmful consequences of artificial intelligence (AI) chatbot use among patients with mental illness: Early data from a large psychiatric service system*. *Acta Psychiatrica Scandinavica, 153*, 301–303. https://doi.org/10.1111/acps.70068

### How source material is used

1. `src/data_processor.py` finds the PDF files in `source_material/`.
2. It extracts readable text from each PDF.
3. The extracted text is combined and sent to the language model.
4. `src/llm_processor.py` generates a structured JSON podcast script.
5. The JSON script is sent to `src/tts_generator.py` for audio generation.

The current script structure contains:

- the episode title;
- speaker segments;
- the speaker name (`Ana` or `Rui`);
- the spoken text for each segment.
