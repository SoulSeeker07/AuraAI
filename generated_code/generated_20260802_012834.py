import os

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")

client = InferenceClient(
    provider="hf-inference",
    api_key=HF_TOKEN,
)

def generate_image(prompt, filename):
    try:
        image = client.text_to_image(
            prompt=prompt,
            model="black-forest-labs/FLUX.1-dev"
            # Other models:
            # "stabilityai/stable-diffusion-xl-base-1.0"
            # "black-forest-labs/FLUX.1-schnell"
        )

        image.save(filename)
        print(f"✅ Saved to {filename}")

    except Exception as e:
        print("❌ Error:", e)


if __name__ == "__main__":
    generate_image(
        "A cinematic portrait of Iron Man, ultra realistic, 8k, glowing arc reactor",
        "ironman.png"
    )