FROM python:3.12-slim-bookworm

# Install required packages
RUN apt-get update && apt-get install -y wget curl

# Set up working directory
WORKDIR /home/code

# Create /code directory
RUN mkdir -p /code

# Download concordium-client package
RUN wget https://distribution.concordium.software/tools/linux/concordium-client_7.0.1-0 -O /code/concordium-client \
    && chmod +x /code/concordium-client

# Download and install rustup
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs > rustup.sh \
    && chmod +x rustup.sh \
    && ./rustup.sh -y \
    && rm rustup.sh

# Add rust to path
ENV PATH="/root/.cargo/bin:${PATH}"

# Install cargo-concordium
RUN cargo install cargo-concordium

# Install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

CMD ["python3", "/home/code/main.py"]