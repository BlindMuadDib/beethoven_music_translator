FROM mmcauliffe/montreal-forced-aligner:latest

WORKDIR /app

USER root
RUN /opt/conda/bin/mamba install -n base flask gunicorn -y

COPY --chown=mfauser:mfauser ./data/corpus /app/corpus
COPY --chown=mfauser:mfauser ./data /app/data

USER mfauser

RUN /env/bin/mfa model download acoustic english_us_arpa
RUN /env/bin/mfa model download dictionary english_us_arpa

WORKDIR /app
COPY --chown=mfauser:mfauser ./aligner_wrapper.py /app/aligner_wrapper.py

EXPOSE 24725

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:24725 || exit 1

# Directly use the Conda environment's Python interpreter
CMD ["/opt/conda/bin/gunicorn", "--bind", "0.0.0.0:24725", "aligner_wrapper:app", "--workers", "3", "--timeout", "600"]
