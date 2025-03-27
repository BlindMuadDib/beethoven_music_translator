"""
Creates a wrapper class then executes the Spleeter `separate`
command within a Docker container

Args:
    input_file (str): The path to the input audio file
    output_dir (str): The path to the output directory
    stems (str, optional): The Spleeter model to use
        Defaults to 4stems-16kHz

Raises:
    FileNotFoundError: If the inpt file or output directory does not exist
    subprocess.CalledProcessError: If the Spleeter command fails
    ValueError: If input arguments are invalid

This project would not be possible without Spleeter by Deezer
Used under the MIT License
GitHub: https://github.com/deezer/spleeter
"""

import subprocess
import os

class SpleeterWrapper:
    """A wrapper class for executing Spleeter commands within a Docker container"""

    def separate(self, input_dir, output_dir, input_file_name):
        """Main function of the wrapper"""
        if not input_dir:
            raise ValueError("Input directory path cannot be None or empty.")

        if not input_file_name:
            raise ValueError("Input file name cannot be None or empty.")

        if not output_dir:
            raise ValueError("Output directory path cannot be None or empty.")

        if not os.path.exists(input_dir):
            raise FileNotFoundError(f"Input directory not found: {input_dir}")

        if not os.path.exists(output_dir):
            raise FileNotFoundError(f"Output direcory not found: {output_dir}")

        input_file_path = os.path.join(input_dir, input_file_name)
        if not os.path.exists(input_file_path):
            raise FileNotFoundError(f"Input file not found: {input_file_path}")

        input_dir_abs = os.path.abspath(input_dir)
        output_dir_abs = os.path.abspath(output_dir)

        command = [
            "docker",
            "run",
            "--rm",
            "-v", f"{input_dir_abs}:/input",
            "-v", f"{output_dir_abs}:/output",
            "researchdeezer/spleeter",
            "separate",
            "-i", f"/input/{input_file_name}",
            "-o", "/output",
            "-p", "spleeter:4stems-16kHz"
        ]

        subprocess.run(command, check=True)
