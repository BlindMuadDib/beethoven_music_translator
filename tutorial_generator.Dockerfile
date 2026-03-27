# container to generate the tutorial assets into Ceph filesystem
FROM python:3.12-slim

# Install dependencies
RUN pip install numpy scipy

# Set working directory
WORKDIR /app

# Copy the utils folder containing the logic
COPY utils/ /app/utils/

# Create the output directory
RUN mkdir -p /tutorial

# Set the environment variable for the script to know where to save
ENV TUTORIAL_OUTPUT_DIR=/tutorial

# Command to run the generation script
CMD ["python", "/app/utils/_generate_tutorial_assets.py"]
