FROM mmcauliffe/montreal-forced-aligner:latest

WORKDIR /app

USER root
RUN /opt/conda/bin/mamba install -n base flask -y
USER mfauser

COPY --chown=mfauser:mfauser . /app

EXPOSE 24725

# Directly use the Conda environment's Python interpreter
CMD ["/opt/conda/bin/python", "/app/aligner_wrapper.py"]
