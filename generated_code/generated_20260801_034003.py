"""
This script prints a message to a file named test.txt.
It handles potential errors during file operations.
"""

import os


def write_to_file(filename, message):
    """
    Writes a given message to a specified file.

    Args:
        filename (str): The name of the file to write to.
        message (str): The message to be written.

    Raises:
        IOError: If an I/O error occurs while writing to the file.
    """
    try:
        # Open the file in write mode, creating it if it doesn't exist
        with open(filename, 'w') as file:
            # Write the message to the file
            file.write(message)
        print(f"Message written to {filename} successfully.")
    except IOError as e:
        # Handle any I/O errors that occur during the file operation
        print(f"Error writing to {filename}: {e}")

def main():
    filename = "test.txt"
    message = "Hello from autonomous agent\n"
    write_to_file(filename, message)

if __name__ == "__main__":
    main()