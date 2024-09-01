FROM python:3.12-slim-bookworm

WORKDIR /home/code
RUN cd /home/code

# Install Python dependencies.
COPY ./requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt
# Copy application files.
COPY . .
#

CMD ["python3", "/home/code/main.py"]