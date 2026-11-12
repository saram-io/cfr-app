FROM python:3.12-slim

# Install official restic CLI plus SMB/NFS/SFTP/Rsync tools for the Agentless Backup Gateway
RUN apt-get update && apt-get install -y --no-install-recommends \
    restic \
    cifs-utils \
    smbclient \
    openssh-client \
    rsync \
    curl \
    ca-certificates \
    bzip2 \
    && rm -rf /var/lib/apt/lists/*

# Install official resticprofile v0.33.1 binary for declarative profile & schedule management
RUN ARCH=$(dpkg --print-architecture) && \
    curl -fsSL "https://github.com/creativeprojects/resticprofile/releases/download/v0.33.1/resticprofile_0.33.1_linux_${ARCH}.tar.gz" \
    | tar -xz -C /usr/local/bin resticprofile && \
    chmod 0755 /usr/local/bin/resticprofile

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tests ./tests

RUN mkdir -p /app/data/repos /app/data/sample_instruments /app/data/restores /app/data/landing_zones /app/data/profiles

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
