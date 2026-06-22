# CPU image for the OD coeff-discovery job on AWS (Batch/Fargate or EC2 `docker run`).
# The discovery is pure numpy (the DETERMINISTIC decoder tier, S39) — no GPU, no torch.
# GPU is only for the FNO-decoder TRAINING path (see aws/train_fno/).
FROM python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir numpy scipy boto3

# the in-container coeff engine + its callers (kept minimal; no E:\refrag, no torch)
COPY odcore/ /app/odcore/
COPY markets_adapter.py _build_alt_winner_labels.py _run_alt_coeffs.py /app/
COPY aws/run_discovery_s3.py /app/

# S3-driven entrypoint: pull 1-sec bins -> label -> discover coeffs -> push index.
ENTRYPOINT ["python", "/app/run_discovery_s3.py"]
