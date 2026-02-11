"""Prompt templates for LLM-based metadata generation."""

SYSTEM_PROMPT = """\
You are a podcast production assistant. Given a transcript, generate structured \
metadata for the episode. Be concise, engaging, and SEO-friendly. \
Always respond with valid JSON matching the requested schema."""

METADATA_PROMPT = """\
Below is the transcript for a podcast episode. Generate the following metadata \
as a JSON object:

1. "title": A catchy, descriptive episode title (max 100 characters). Do NOT \
   include the podcast name or episode number.
2. "description": A compelling 2-3 sentence episode description for podcast apps.
3. "show_notes": Detailed show notes in Markdown format with key topics, \
   takeaways, and any resources mentioned.
4. "tags": A list of {max_tags} relevant tags/keywords for discoverability.
5. "summary": A one-sentence summary of the episode.
{chapters_instruction}

Respond ONLY with a valid JSON object. No markdown fences, no explanation.

---
TRANSCRIPT:

{transcript}
"""

CHAPTERS_INSTRUCTION = """\
6. "chapters": A list of chapter markers, each with "start_time" (float seconds) \
   and "title" (string). Identify 4-10 major topic transitions. Use the timestamps \
   from the transcript."""

NO_CHAPTERS_INSTRUCTION = """\
6. "chapters": Return an empty list []."""


def build_metadata_prompt(
    transcript_text: str,
    max_tags: int = 10,
    generate_chapters: bool = True,
) -> str:
    chapters_instruction = (
        CHAPTERS_INSTRUCTION if generate_chapters else NO_CHAPTERS_INSTRUCTION
    )
    return METADATA_PROMPT.format(
        transcript=transcript_text,
        max_tags=max_tags,
        chapters_instruction=chapters_instruction,
    )
