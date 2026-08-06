import os

import torch
from diffusers import StableDiffusionPipeline
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the Hugging Face API token from the environment variables
HUGGING_FACE_API_TOKEN = os.getenv("HUGGING_FACE_API_TOKEN")

# Set up the Stable Diffusion pipeline
def generate_image(prompt):
    """
    Generate an image using the Stable Diffusion pipeline.

    Args:
    prompt (str): The prompt to generate an image for.

    Returns:
    None
    """
    # Set up the pipeline
    pipe = StableDiffusionPipeline.from_pretrained(
        "CompVis/stable-diffusion-v1-4", 
        use_auth_token=HUGGING_FACE_API_TOKEN
    )

    # Move the pipeline to the GPU if available
    if torch.cuda.is_available():
        pipe.to("cuda")

    # Generate the image
    image = pipe(prompt).images[0]

    # Save the image
    image.save("ironman.png")

# Generate an image of Ironman
if __name__ == "__main__":
    try:
        generate_image("Ironman in a suit")
        print("Image generated successfully!")
    except Exception as e:
        print(f"Error generating image: {e}")