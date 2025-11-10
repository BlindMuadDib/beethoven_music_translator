FROM mmcauliffe/montreal-forced-aligner:latest

WORKDIR /app

USER root
RUN /opt/conda/bin/mamba install -n base flask gunicorn gevent -y
USER mfauser

RUN /env/bin/mfa model download acoustic english_us_arpa
RUN /env/bin/mfa model download dictionary english_us_arpa

WORKDIR /app
COPY --chown=mfauser:mfauser ./musictranslator/aligner_wrapper.py /app/aligner_wrapper.py

EXPOSE 24725

# Directly use the Conda environment's Python interpreter
CMD ["/opt/conda/bin/gunicorn", "--bind", "0.0.0.0:24725", "aligner_wrapper:app", "--worker-class", "gevent", "--workers", "1", "--worker-connections", "100", "--timeout", "1200"]
