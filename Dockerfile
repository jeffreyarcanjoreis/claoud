# Imagem de produção do Kairos (FastAPI + Uvicorn).
#
# Roda a partir do código-fonte (instalação editável): o runner de migrações
# procura `alembic.ini` e `migrations/` ao lado do pacote `kairos`, então o
# pacote não pode ir para o site-packages sozinho.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml README.md alembic.ini ./
COPY kairos ./kairos
COPY migrations ./migrations

RUN pip install -e .

# Produção por padrão: liga a trava de configuração (config.verificar_producao).
# Fotos, vídeos e anexos vão para KAIROS_DATA_DIR — monte um disco persistente
# nesse caminho, senão os arquivos somem a cada deploy.
ENV KAIROS_ENV=production \
    KAIROS_DATA_DIR=/var/data

EXPOSE 8000

# O provedor injeta $PORT; --proxy-headers respeita o HTTPS do proxy da frente.
CMD ["sh", "-c", "exec uvicorn kairos.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
