import os

import dotenv
import numpy as np
import torch
from huggingface_hub import HfApi, Repository
from huggingface_hub.inference import InferenceClient
from PIL import Image

# Load environment variables from .env file
dotenv.load_dotenv()

# Get Hugging Face token from .env file
HF_TOKEN = os.getenv("HF_TOKEN")

# Set up Hugging Face Inference API client
inference_client = InferenceClient(
    repo_id="runwayml/stable-diffusion-v1-inference",
    token=HF_TOKEN,
)

# Define the prompt for generating the image
prompt = "Ironman in a futuristic city"

# Generate the image using the Inference API
result = inference_client(prompt)

# Get the generated image
image = result.images[0]

# Save the image to a file
image.save("ironman.png")

# Display the generated image
img = Image.open("ironman.png")
img.show()