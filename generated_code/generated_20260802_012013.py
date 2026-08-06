# Import necessary libraries
import os

import pandas as pd
from diffusers import StableDiffusionPipeline
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Define the function to generate an image
def generate_image(prompt):
    """
    Generate an image using the Stable Diffusion model.

    Args:
    prompt (str): The prompt to generate an image for.

    Returns:
    None
    """
    # Initialize the Stable Diffusion pipeline
    model_id = os.getenv("MODEL_ID")
    pipe = StableDiffusionPipeline.from_pretrained(model_id, torch_dtype="float16")

    # Move the pipeline to the GPU if available
    if torch.cuda.is_available():
        pipe.to("cuda")

    # Generate the image
    image = pipe(prompt).images[0]

    # Save the image
    image.save("ironman.png")

# Define the main function
def main():
    # Define the prompt
    prompt = "Ironman in a futuristic city"

    # Generate the image
    generate_image(prompt)

    print("Image generated and saved as ironman.png")

# Run the main function
if __name__ == "__main__":
    import torch
    main()