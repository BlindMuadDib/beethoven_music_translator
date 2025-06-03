FROM mmcauliffe/montreal-forced-aligner:latest

WORKDIR /app

USER root
RUN /opt/conda/bin/mamba install -n base flask gunicorn -y
USER mfauser

RUN /env/bin/mfa model download acoustic english_us_arpa
RUN /env/bin/mfa model download dictionary english_us_arpa

WORKDIR /app
COPY --chown=mfauser:mfauser ./musictranslator/aligner_wrapper.py /app/aligner_wrapper.py

EXPOSE 24725

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:24725 || exit 1

# Directly use the Conda environment's Python interpreter
CMD ["/opt/conda/bin/gunicorn", "--bind", "0.0.0.0:24725", "aligner_wrapper:app", "--workers", "3", "--timeout", "600"]
