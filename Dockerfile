FROM python:3.12-slim-bookworm
# Add a step to install wget
RUN apt-get update && apt-get install -y wget

WORKDIR /home/code
# download concordium-client package
RUN wget https://distribution.concordium.software/tools/linux/concordium-client_7.0.1-0 -O /code/concordium-client && chmod +x /code/concordium-client

# download rustup install script
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs > /code/rustup.sh && chmod +x /code/rustup.sh

# install rustup
RUN /home/code/rustup.sh -y
RUN rm /home/code/rustup.sh

# add rust to path
ENV PATH="/root/.cargo/bin:${PATH}"

# install cargo-concordium
RUN cargo install cargo-concordium


WORKDIR /home/code
RUN cd /home/code

# Install Python dependencies.
COPY ./requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt
# Copy application files.
COPY . .
#

CMD ["python3", "/home/code/main.py"]