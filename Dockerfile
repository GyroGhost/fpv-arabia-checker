# ---------- المرحلة ١: بناء BlackBox_CSV_Render من الكود ----------
FROM rust:1-bookworm AS bbr
ARG BBR_REPO=https://github.com/nerdCopter/BlackBox_CSV_Render.git
# نثبت نسخة معينة عشان التحديثات ما تخرب البوت فجأة. للتحديث: غيّر الرقم
ARG BBR_REF=dc2aa97
RUN apt-get update \
 && apt-get install -y --no-install-recommends libfontconfig1-dev libfreetype6-dev \
 && rm -rf /var/lib/apt/lists/*
RUN git clone "$BBR_REPO" /src \
 && cd /src && git checkout "$BBR_REF" \
 && cargo build --release \
 && cp target/release/BlackBox_CSV_Render /BlackBox_CSV_Render

# ---------- المرحلة ٢: البوت ----------
FROM python:3.12-slim-bookworm
RUN apt-get update \
 && apt-get install -y --no-install-recommends libfontconfig1 libfreetype6 \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --from=bbr /BlackBox_CSV_Render /usr/local/bin/BlackBox_CSV_Render
COPY . .
ENV RENDER_BIN=/usr/local/bin/BlackBox_CSV_Render \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg
CMD ["python", "bot.py"]
