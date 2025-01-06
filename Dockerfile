FROM python:3.12-slim-bookworm

# Install required packages and build dependencies
RUN apt-get update && \
    apt-get install -y \
    wget \
    curl \
    build-essential \
    pkg-config \
    libssl-dev \
    git \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory and tmp directory
WORKDIR /home/code
RUN mkdir -p /home/code/tmp && chmod 777 /home/code/tmp


# Download concordium-client package
RUN wget https://distribution.concordium.software/tools/linux/concordium-client_7.0.1-0 -O /code/concordium-client \
    && chmod +x /code/concordium-client

# Download and install rustup with cargo
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Add wasm target
RUN rustup target add wasm32-unknown-unknown

# Install cargo-concordium
RUN cargo install --locked cargo-concordium

# Install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

CMD ["python3", "/home/code/main.py"]