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
    # Read the CSV file (not required for this task, but added as per previous conversation context)
    try:
        df = pd.read_csv("data.csv")
        print("Average of the second column:", df.iloc[:, 1].mean())
    except FileNotFoundError:
        print("The file data.csv was not found.")
    except Exception as e:
        print("An error occurred:", str(e))

    # Generate an image of Ironman
    prompt = "Ironman in a suit"
    generate_image(prompt)

# Run the main function
if __name__ == "__main__":
    import torch
    main()