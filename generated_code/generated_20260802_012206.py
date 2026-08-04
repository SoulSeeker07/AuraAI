import os
from huggingface_hub import HfApi, Repository
from diffusers import StableDiffusionPipeline
from PIL import Image
import numpy as np
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get Hugging Face token from .env file
HF_TOKEN = os.getenv("HF_TOKEN")

# Set up the Hugging Face API
api = HfApi(token=HF_TOKEN)

# Set up the Stable Diffusion pipeline using the Hugging Face Inference API
pipe = StableDiffusionPipeline.from_pretrained("CompVis/stable-diffusion-v1-4", use_auth_token=HF_TOKEN)

# Define the prompt for generating the image
prompt = "Ironman in a futuristic city"

# Generate the image
image = pipe(prompt).images[0]

# Save the image to a file
image.save("ironman.png")

# Display the generated image
image = Image.open("ironman.png")
image.show()