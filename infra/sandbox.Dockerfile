# Sandbox image for the Modeling R&D loop — the Engineer agent's generated code runs here,
# with no network and strict resource/time limits (enforced by the executor at launch).
# Reproducibility: this image digest becomes part of each Run's manifest.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

RUN pip install --no-cache-dir \
    numpy pandas scipy \
    scikit-learn statsmodels \
    xgboost lightgbm \
    matplotlib \
    sktime pmdarima
# Deep Learning (PyTorch, CPU) is heavy — enable when the DL sandbox path is exercised:
# RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Unprivileged user; the executor mounts only the run's data dir and drops the network.
RUN useradd --create-home --uid 10001 sandbox
USER sandbox
WORKDIR /work

CMD ["python"]
