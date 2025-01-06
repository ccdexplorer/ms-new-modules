FROM python:3.12-slim-bookworm

# Add build essentials for Rust compilation
RUN apt-get update && \
    apt-get install -y \
    build-essential \
    pkg-config \
    libssl-dev \
    git \
    cmake \
    && rustup target add wasm32-unknown-unknown \
    && cargo install --locked cargo-concordium

# Set up working directory and create necessary directories
WORKDIR /home/code
RUN mkdir -p /home/code/tmp && \
    chmod 777 /home/code/tmp && \
    mkdir -p /home/code/bin

# Download concordium-client package
RUN wget --no-verbose https://distribution.concordium.software/tools/linux/concordium-client_7.0.1-0 -O /home/code/bin/concordium-client && \
    chmod +x /home/code/bin/concordium-client

# Add concordium-client to PATH
ENV PATH="/home/code/bin:${PATH}"

# Download and install rustup with cargo
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Add wasm target and install cargo-concordium
RUN rustup target add wasm32-unknown-unknown && \
    cargo install --locked cargo-concordium

# Install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

CMD ["python3", "/home/code/main.py"]