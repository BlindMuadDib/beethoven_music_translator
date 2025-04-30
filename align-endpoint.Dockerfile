FROM mmcauliffe/montreal-forced-aligner:latest

WORKDIR /app

USER root
RUN /opt/conda/bin/mamba install -n base flask -y
USER mfauser

COPY --chown=mfauser:mfauser aligner_wrapper.py /app

EXPOSE 24725

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:24725 || exit 1

# Directly use the Conda environment's Python interpreter
CMD ["/opt/conda/bin/python", "/app/aligner_wrapper.py"]
