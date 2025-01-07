FROM python:3.12-slim-bookworm

# Install Docker and dependencies
RUN apt-get update && \
    apt-get install -y \
    wget \
    curl \
    build-essential \
    pkg-config \
    libssl-dev \
    git \
    cmake \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release && \
    # Add Docker's official GPG key
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg && \
    # Set up Docker repository
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null && \
    # Install Docker
    apt-get update && \
    apt-get install -y docker-ce docker-ce-cli containerd.io && \
    # Cleanup
    rm -rf /var/lib/apt/lists/*
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

# Add user to docker group
RUN groupadd docker || true && \
    usermod -aG docker root

CMD ["python3", "/home/code/main.py"]