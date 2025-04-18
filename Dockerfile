FROM python:3.10-slim

# Instala Chrome
RUN apt-get update && apt-get install -y wget unzip curl gnupg \
    && curl -sSL https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Actualiza pip
RUN pip install --no-cache-dir --upgrade pip

# Copia los archivos de dependencias e instala paquetes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del proyecto
COPY . /app
WORKDIR /app

# Ejecuta tu bot
CMD ["python", "main.py"]
