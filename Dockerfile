# Use an official Python runtime as a parent image
FROM tiangolo/uvicorn-gunicorn-fastapi

# RUN apk add --no-cache build-base curl libffi-dev zlib-dev postgresql-dev make libffi libpq

# Set the working directory to /app
WORKDIR /app

COPY Pipfile* /app/

# Install any needed packages specified in Pipfile
RUN pip install pipenv && pipenv install --system

# Copy the current directory contents into the container at /app
COPY . /app

# Make port 8080 available to the world outside this container
EXPOSE $PORT

# Run app.py when the container launches

CMD uvicorn fast_api:app --port=$PORT --host=0.0.0.0
