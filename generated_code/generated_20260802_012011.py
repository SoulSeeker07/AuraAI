# Import necessary libraries
import os

import pandas as pd
from diffusers import StableDiffusionPipeline
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Define the function to generate an image
def generate_image():
    # Load the Stable Diffusion pipeline
    model_id = "CompVis/stable-diffusion-v1-4"
    pipe = StableDiffusionPipeline.from_pretrained(model_id, torch_dtype="float16")

    # Move the pipeline to the GPU if available
    if torch.cuda.is_available():
        pipe.to("cuda")

    # Define the prompt for the image generation
    prompt = "Ironman"

    # Generate the image
    image = pipe(prompt).images[0]

    # Save the image to a file
    image.save("ironman.png")

# Define the main function
def main():
    try:
        # Generate the image
        generate_image()
        print("Image generated successfully!")
    except Exception as e:
        print(f"An error occurred: {e}")

# Run the main function
if __name__ == "__main__":
    main()