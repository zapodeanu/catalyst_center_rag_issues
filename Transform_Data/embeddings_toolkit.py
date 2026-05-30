import logging
import os
import warnings

import certifi
import numpy as np
from dotenv import load_dotenv

# Keep these before transformer imports so progress/log noise stays quiet.
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TQDM_DISABLE", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

from sentence_transformers import SentenceTransformer

__author__ = "Gabriel Zapodeanu, Principal TME"
__copyright__ = "Copyright (c) 2026 Cisco and/or its affiliates."


def main():
    # Keep this utility quiet by default.
    logging.basicConfig(level=logging.CRITICAL)
    warnings.filterwarnings("ignore")
    for noisy_logger in (
        "httpx",
        "httpcore",
        "sentence_transformers",
        "huggingface_hub",
        "transformers",
        "urllib3",
    ):
        logger = logging.getLogger(noisy_logger)
        logger.setLevel(logging.CRITICAL)
        logger.disabled = True

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(base_dir, "environment.env")
    load_dotenv(env_path)

    ca_bundle = (
        os.getenv("HF_CA_BUNDLE")
        or os.getenv("REQUESTS_CA_BUNDLE")
        or os.getenv("SSL_CERT_FILE")
    )
    if not ca_bundle:
        default_local_bundle = os.path.expanduser("~/hf-ca-bundle.pem")
        ca_bundle = default_local_bundle if os.path.isfile(default_local_bundle) else certifi.where()
    os.environ["SSL_CERT_FILE"] = ca_bundle
    os.environ["REQUESTS_CA_BUNDLE"] = ca_bundle

    model_name = os.getenv("MODEL_LOCAL_PATH") or os.getenv("MODEL_NAME") or "sentence-transformers/all-MiniLM-L6-v2"
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output.txt")

    sentences = [
        "The device: PDX-RO details\n Hostname: PDX-RO\n Location: Global/OR/PDX/Floor-2\n Device Role: BORDER ROUTER"
    ]

    print("\n\n" + sentences[0] + "\n")
    print(f"Embedding model: {model_name}")
    try:
        model = SentenceTransformer(model_name)
    except Exception as exc:
        raise RuntimeError(
            "Unable to load embedding model from HuggingFace. "
            "Set HF_CA_BUNDLE in environment.env for corporate TLS proxies, "
            "or set MODEL_LOCAL_PATH for offline use. "
            f"MODEL_NAME currently: {os.getenv('MODEL_NAME', 'not set')}. "
            f"Original error: {exc}"
        ) from exc

    embeddings = model.encode(sentences)[0]
    print(f"Embedding length: {len(embeddings)}")
    np.savetxt(output_path, embeddings)
    print(f"Embedding vector saved to: {output_path}\n")

    print(embeddings)


if __name__ == "__main__":
    main()