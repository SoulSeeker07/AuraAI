import os

import torch
from diffusers import StableDiffusionPipeline
from dotenv import load_dotenv
from huggingface_hub import HfApi, Repository
from PIL import Image

# Load environment variables from .env file
load_dotenv()

# Get the Hugging Face token from the environment variables
HF_TOKEN = os.getenv("HF_TOKEN")

# Set up the Hugging Face API
api = HfApi(token=HF_TOKEN)

# Set up the Stable Diffusion pipeline
model_id = "CompVis/stable-diffusion-v1-4"
pipe = StableDiffusionPipeline.from_pretrained(model_id, torch_dtype=torch.float16)

# Use the pipeline to generate an image of Iron Man
prompt = "Iron Man in a suit of armor"
image = pipe(prompt).images[0]

# Save the generated image
image.save("ironman.png")

# Display the generated image
image = Image.open("ironman.png")
image.show()