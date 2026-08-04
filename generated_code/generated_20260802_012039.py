import os
from huggingface_hub import HfApi, Repository
from diffusers import StableDiffusionPipeline
from PIL import Image
import numpy as np
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the Hugging Face token from the environment variables
HF_TOKEN = os.getenv("HF_TOKEN")

# Set up the Hugging Face API client
api = HfApi(token=HF_TOKEN)

# Define the model and parameters
model_id = "CompVis/stable-diffusion-v1-4"
prompt = "Ironman in a suit of armor"

# Create a Stable Diffusion pipeline using the Hugging Face Inference API
pipe = StableDiffusionPipeline.from_pretrained(model_id, use_auth_token=HF_TOKEN)

# Generate an image using the pipeline
image = pipe(prompt).images[0]

# Save the image to a file
image.save("ironman.png")

# Display the generated image
img = Image.open("ironman.png")
img.show()