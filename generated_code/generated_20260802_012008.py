# Import necessary libraries
import os
import pandas as pd
from dotenv import load_dotenv
from diffusers import StableDiffusionPipeline

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
    api_key = os.getenv("API_KEY")
    pipe = StableDiffusionPipeline.from_pretrained(model_id, use_auth_token=api_key)

    # Generate the image
    image = pipe(prompt).images[0]

    # Save the image
    image.save("ironman.png")

# Define the main function
def main():
    # Define the prompt
    prompt = "Ironman"

    # Generate the image
    generate_image(prompt)

    # Print a success message
    print("Image generated successfully!")

# Run the main function
if __name__ == "__main__":
    main()