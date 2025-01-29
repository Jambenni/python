# Use an official Python runtime as a parent image
FROM python:3.9

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 8080
EXPOSE 8080

# Define environment variable
ENV FLASK_APP=app.py

# Run the application
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8080", "app:app"]

