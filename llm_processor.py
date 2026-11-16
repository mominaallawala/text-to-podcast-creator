# to allow json to give structure to our two host podcast
import json
from openai import OpenAI

from src.hosts import HOSTS


SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string"
        },
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {
                        "type": "string",
                        "enum": ["Ana", "Rui"]
                    },
                    "text": {
                        "type": "string"
                    }
                },
                "required": ["speaker", "text"],
                "additionalProperties": False
            }
        }
    },
    "required": ["title", "segments"],
    "additionalProperties": False
}

def build_podcast_prompt(
    source_text: str,
    episode_title: str = "AI Apocalypse?",
    source_details: str = "",
) -> str:
    host_details = "\n".join(
        f"- {name}: {details['role']}"
        for name, details in HOSTS.items()
    )

    return f"""
You are writing one podcast episode titled "{episode_title}".

Opening requirements:
- Ana must introduce herself by name and welcome the audience.
- Rui must introduce himself by name.
- Together, they must introduce the episode topic.
- They must briefly explain what the audience will learn.
- The introduction should sound natural and conversational.
- In the introduction, briefly mention the source papers that inform this episode.
- Name the authors and publication titles only when that information appears in the source material.
- Explain that the episode compares their different perspectives.
- Do not repeat the source names in every line.
- Do not add source citations to ordinary questions, reactions, or transitions.

Audience:
Experienced professionals who are AI-curious. They are smart and busy. Avoid basic explanations, buzzwords, and unnecessary hand-holding.

Tone:
Informative, balanced, curious, and conversational. Discuss AI risks seriously without sensationalism or fear-mongering.

Always distinguish between:
- evidence or expert consensus
- plausible risks or open debate
- speculation or hype

Hosts:
{host_details}

Length:
Aim for approximately 900 words of spoken dialogue, with an acceptable
range of 750–1050 words.

Keep the hook and introduction to about 100 words combined.

Structure and emphasis:
1. Hook and introduction — about 100 words total.
   Ana and Rui should introduce themselves, welcome listeners, introduce the
   topic, explain what the episode will cover, and briefly mention the sources.
   Keep greetings and transitions brief.

2. Mental health paper — about 200 words.
   Explain what the researchers observed, what evidence they used, and what
   conclusions the evidence supports. Clearly distinguish observations from
   interpretation and avoid claiming causation if the paper does not establish it.

3. Existential risk paper — about 200 words.
   Explain one assumption examined by the authors, why it matters, and what
   the authors say remains uncertain. Distinguish evidence, plausible risk,
   debate, and speculation.

4. Comparison — about 200 words.
   Explain how the papers ask different questions and what listeners can take
   away from each paper. Make the comparison clear without repeating the same points.

5. Practical implications, recap, and closing — about 200 words combined.
   Explain what professionals should consider, give three distinct key
   takeaways, thank the listeners, and close the episode. Avoid repeating
   takeaways or earlier explanations.

Expand the discussion using details from the supplied papers. Do not invent
facts, names, statistics, or conclusions. Use only information supported by
the source material.

Rules:
- Use only facts, names, and numbers from the source material.
- Do not invent information.
- Write for spoken audio using short, natural sentences.
- Do not use markdown, bullet points, URLs, or stage directions.
- Mention the sources naturally when relevant.
- Label every line as either "Ana:" or "Rui:".
- Return only a JSON object with the keys "title" and "segments".

Each segment must contain:
- "speaker": either "Ana" or "Rui"
- "text": the spoken dialogue

Do not return markdown or any text outside the JSON object.

Source details:
{source_details}

Attribution rules:
- When introducing a paper's main finding or argument, credit its authors
  and refer to the paper by its published article title when that title is
  available.
- When comparing papers, say which authors made each claim.
- Credit statistics and direct quotes to the paper they came from.
- Use the author's surname for later mentions when it is clear which paper you mean.
- If an author or title is missing, refer to the paper by its known details.
- Never guess missing details.
- Never say "et al." aloud. When several authors are credited together,
  say "and colleagues" instead.
- Do not refer to a paper by its journal or publication name when introducing
  it; use the article title instead.

Source coverage:
- Mention all three supplied papers at least once in the episode.
- Identify each paper by an author's surname or by its known title.
- Publication names are optional and are not required for source coverage.
- The comparison section does not need to discuss all three papers.

Source material:
{source_text}
""".strip()

def generate_podcast_script(
    client: OpenAI,
    source_text: str,
    episode_title: str = "AI Apocalypse?",
    source_details: str = "",
) -> dict:
    """
    Send source material to the OpenAI API and return the script.
    """
    prompt = build_podcast_prompt(
        source_text=source_text,
        episode_title=episode_title,
        source_details=source_details,
    )

    # Make one structured request and return the transcript so it can be
    # reviewed in the notebook and displayed by the interface.
    response = client.responses.create(
        model="gpt-4o",
        input=prompt,
        text={
            "format": {
                "type": "json_schema",
                "name": "podcast_script",
                "schema": SCRIPT_SCHEMA,
                "strict": True,
            }
        },
    )

    script = json.loads(response.output_text)

    if not script.get("segments"):
        raise ValueError("The LLM returned a script with no dialogue.")

    word_count = sum(
        len(segment["text"].split())
        for segment in script["segments"]
    )
    print(f"Script length: {word_count} words")

    if word_count < 750 or word_count > 1050:
        print("Warning: script is outside the target range of 750-1050 words.")

    return script
