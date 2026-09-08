import time
import json
from dotenv import load_dotenv
from PIL import Image, ImageDraw
import io

load_dotenv(override=True)
import sys
sys.path.insert(0, "src")

from ai.key_pool import KeyPool
from google import genai
from google.genai import types

def main():
    pool = KeyPool.get_instance()
    key = pool.get_active_key("gemini")
    client = genai.Client(api_key=key)

    # 1. Create a simulated 1080p web browser page (1920x1080)
    webpage = Image.new("RGB", (1920, 1080), color="#f8f9fa")
    draw = ImageDraw.Draw(webpage)
    # Header bar
    draw.rectangle([(0, 0), (1920, 60)], fill="#e9ecef")
    # Search input bar
    draw.rectangle([(500, 15), (1400, 48)], fill="#ffffff", outline="#ced4da")
    # Blue Sign In button
    draw.rectangle([(1750, 15), (1880, 48)], fill="#0d6efd")
    # Main content card
    draw.rectangle([(300, 150), (1620, 900)], fill="#ffffff", outline="#dee2e6")

    buf = io.BytesIO()
    webpage.save(buf, format="PNG")
    part = types.Part.from_bytes(data=buf.getvalue(), mime_type="image/png")

    agent_prompt = (
        "You are an autonomous browser agent.\n"
        "User goal: 'Sign in to my account'.\n"
        "Look at this 1920x1080 browser screenshot.\n"
        "Identify the target element to achieve this goal, its coordinates [ymin, xmin, ymax, xmax] (0-1000 scale), and the action.\n"
        "Return ONLY raw JSON with keys: thought, action, box_2d, target_description."
    )

    t0 = time.perf_counter()
    resp = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=[agent_prompt, part],
        config=types.GenerateContentConfig(temperature=0.0)
    )
    dur = time.perf_counter() - t0

    print(f"Autonomous Browser Step Latency: {dur:.2f}s")
    print(f"Prompt Tokens: {resp.usage_metadata.prompt_token_count}")
    print(f"Candidate Tokens: {resp.usage_metadata.candidates_token_count}")
    print(f"Total Tokens: {resp.usage_metadata.total_token_count}")
    print("\nDecision Output:")
    print(resp.text)

if __name__ == "__main__":
    main()
