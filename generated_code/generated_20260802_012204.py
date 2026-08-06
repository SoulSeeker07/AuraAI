import os

import torch
from diffusers import StableDiffusionPipeline
from dotenv import load_dotenv
from huggingface_hub import HfApi, Repository
from huggingface_hub.inference import InferenceClient
from PIL import Image

# Load environment variables from .env file
load_dotenv()

# Get Hugging Face token from .env file
HF_TOKEN = os.getenv("HF_TOKEN")

# Set up the Hugging Face API and Inference Client
api = HfApi(token=HF_TOKEN)
inference_client = InferenceClient(token=HF_TOKEN)

# Define the model and prompt
model_id = "CompVis/stable-diffusion-v1-4"
prompt = "Ironman in a futuristic city"

# Use the Inference Client to generate an image
with inference_client(model_id, api=api) as client:
    image = client.generate(prompt)

# Save the generated image to a file
image.save("ironman.png")

# Display the generated image
img = Image.open("ironman.png")
img.show()