import requests
import json
import re
from config import OLLAMA_URL, OLLAMA_MODEL, DEFAULT_HASHTAGS


def _call_ollama(prompt: str) -> str:
    """Call Ollama API and return the response text."""
    response = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["response"].strip()


def generate_script_and_metadata(topic: str) -> dict:
    """Generate script split into 4 sections, each with a matching clip keyword.

    Returns dict with:
        - script: full narration text
        - sections: list of 4 dicts with {narration, clip_keyword}
        - title, description, hashtags
    """
    prompt = f"""You are creating a YouTube Shorts video about: "{topic}"

The video is 28-30 seconds, with 4 sections. Each section has narration + a matching video clip.

Return a JSON object with these fields:
- "title": catchy YouTube title (max 60 chars, no hashtags)
- "description": 2-3 sentence description
- "hashtags": exactly 3 trending hashtags related to the topic (each starting with #)
- "sections": an array of exactly 4 objects, each with:
  - "narration": the voiceover text for this section (15-20 words each)
  - "clip_keyword": a 2-3 word search query to find a matching stock video clip for this section

Section 1 MUST be a hook (5-6 seconds). Make it dramatic/fun to stop scrolling.
Hook style example: "Animals you haven't seen as babies... like and subscribe if this puppy is cute or this spider will be in your bed tonight"
Sections 2-4 are facts/points (~7 seconds each).

IMPORTANT: The clip_keyword MUST visually match what the narration is describing.
For example:
- If narration says "baby elephants weigh 250 pounds at birth" → clip_keyword: "baby elephant"
- If narration says "newborn pandas are pink and tiny" → clip_keyword: "newborn panda"
- If narration says "kittens are born with closed eyes" → clip_keyword: "newborn kitten"

Total narration should be 70-80 words across all 4 sections.

Return ONLY valid JSON. No markdown, no explanation.
Example:
{{"title": "Baby Animals That Will Melt Your Heart", "description": "...", "hashtags": ["#BabyAnimals", "#CuteAnimals", "#Wildlife"], "sections": [{{"narration": "...", "clip_keyword": "baby elephant"}}, {{"narration": "...", "clip_keyword": "newborn panda"}}, {{"narration": "...", "clip_keyword": "baby kitten"}}, {{"narration": "...", "clip_keyword": "puppy dog"}}]}}"""

    raw = _call_ollama(prompt)

    # Parse JSON
    try:
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
        else:
            data = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback
        data = {
            "title": topic[:60],
            "description": f"Amazing facts about {topic}!",
            "hashtags": [f"#{topic.replace(' ', '')}"],
            "sections": [
                {"narration": f"You won't believe these facts about {topic}!", "clip_keyword": topic},
                {"narration": f"First, {topic} are truly incredible creatures.", "clip_keyword": topic},
                {"narration": f"Second, they have amazing abilities.", "clip_keyword": topic},
                {"narration": f"Follow for more amazing {topic} facts!", "clip_keyword": topic},
            ],
        }

    # Ensure we have 4 sections
    sections = data.get("sections", [])
    while len(sections) < 4:
        sections.append({"narration": f"Amazing facts about {topic}!", "clip_keyword": topic})
    sections = sections[:4]
    data["sections"] = sections

    # Build full script from sections
    data["script"] = " ".join(s["narration"] for s in sections)

    # Extract keywords in order (one per section)
    data["keywords"] = [s["clip_keyword"] for s in sections]

    # Append default hashtags
    existing_hashtags = data.get("hashtags", [])
    for tag in DEFAULT_HASHTAGS:
        if tag not in existing_hashtags:
            existing_hashtags.append(tag)
    data["hashtags"] = existing_hashtags

    return data
