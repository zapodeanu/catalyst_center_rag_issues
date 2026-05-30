#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Copyright (c) 2026 Cisco and/or its affiliates.
This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at
               https://developer.cisco.com/docs/licenses
All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.
"""

__author__ = "Gabriel Zapodeanu, Principal TME"
__email__ = "gzapodea@cisco.com"
__version__ = "0.1.0"
__copyright__ = "Copyright (c) 2026 Cisco and/or its affiliates."
__license__ = "Cisco Sample Code License, Version 1.1"

import logging
import os
import certifi
import chromadb
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("chromadb.telemetry").setLevel(logging.WARNING)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, "environment.env")
load_dotenv(ENV_PATH)

# database server details
DB_SERVER = os.getenv("DB_SERVER")
DB_PORT = os.getenv("DB_PORT")
DB_COLLECTION = os.getenv("DB_COLLECTION")
APPS_PATH = os.getenv("APPS_PATH")
DATASET = os.getenv("DATASET")

# Embeddings model
MODEL_NAME = os.getenv("MODEL_NAME")
MODEL_LOCAL_PATH = os.getenv("MODEL_LOCAL_PATH")
HF_CA_BUNDLE = os.getenv("HF_CA_BUNDLE")


def ensure_env_config():
    required = {
        "DB_SERVER": DB_SERVER,
        "DB_PORT": DB_PORT,
        "DB_COLLECTION": DB_COLLECTION,
        "APPS_PATH": APPS_PATH,
        "DATASET": DATASET,
    }
    for key, value in required.items():
        if not value:
            raise ValueError(f"{key} is not set in environment.env")
    if not MODEL_NAME and not MODEL_LOCAL_PATH:
        raise ValueError("Set MODEL_NAME or MODEL_LOCAL_PATH in environment.env")


def dataset_path_from_env():
    if os.path.isabs(DATASET):
        return DATASET
    return os.path.join(APPS_PATH, DATASET)


def load_docs(directory):
    documents = []
    for filename in sorted(os.listdir(directory)):
        file_path = os.path.join(directory, filename)
        if not os.path.isfile(file_path):
            continue
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            documents.append(
                Document(
                    page_content=f.read(),
                    metadata={"source": file_path, "filename": filename},
                )
            )
    return documents


def split_docs(document, chunk_size, chunk_overlap, separator, file):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap, separators=separator
    )
    split_documents = text_splitter.split_documents(document)

    # Preserve original metadata convention: device_issue_command
    file_details = file.split("_")
    device_name = file_details[0] if len(file_details) > 0 else "unknown"
    issue_name = file_details[1] if len(file_details) > 1 else "unknown"
    command = file_details[2].replace("-", " ") if len(file_details) > 2 else "unknown"

    chunk_number = 1
    for doc in split_documents:
        doc.metadata["chunk_number"] = chunk_number
        doc.metadata["device name"] = device_name
        doc.metadata["issue name"] = issue_name
        doc.metadata["CLI command"] = command
        chunk_number += 1

    return split_documents


def load_file(filename, path):
    file_path = os.path.join(path, filename)
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return [Document(page_content=f.read(), metadata={"source": file_path, "filename": filename})]


def create_doc_embeddings(document, file, embeddings):
    chroma_db_server = chromadb.HttpClient(host=DB_SERVER, port=int(DB_PORT))
    docs = split_docs(document=document, chunk_size=100, chunk_overlap=25, separator="!", file=file)

    Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        client=chroma_db_server,
        collection_name=DB_COLLECTION,
    )

    chroma_collection = Chroma(client=chroma_db_server, collection_name=DB_COLLECTION)
    return chroma_collection._collection.count()


def main():
    ensure_env_config()

    ca_bundle = (
        HF_CA_BUNDLE
        or os.getenv("REQUESTS_CA_BUNDLE")
        or os.getenv("SSL_CERT_FILE")
    )
    if not ca_bundle:
        default_local_bundle = os.path.expanduser("~/hf-ca-bundle.pem")
        ca_bundle = default_local_bundle if os.path.isfile(default_local_bundle) else certifi.where()
    os.environ["SSL_CERT_FILE"] = ca_bundle
    os.environ["REQUESTS_CA_BUNDLE"] = ca_bundle

    dataset_path = dataset_path_from_env()
    if not os.path.isdir(dataset_path):
        raise ValueError(f"DATASET path not found: {dataset_path}")

    logging.info("Target Chroma server: %s:%s", DB_SERVER, DB_PORT)
    logging.info("Target collection: %s", DB_COLLECTION)
    effective_model_name = MODEL_LOCAL_PATH if MODEL_LOCAL_PATH else MODEL_NAME
    logging.info("Embedding model: %s", effective_model_name)
    logging.info("Dataset folder: %s", dataset_path)

    documents = load_docs(dataset_path)
    logging.info("There are %s documents in the folder", len(documents))

    chroma_db = chromadb.HttpClient(host=DB_SERVER, port=int(DB_PORT))
    chroma_db.heartbeat()

    embeddings = HuggingFaceEmbeddings(model_name=effective_model_name)
    files_list = sorted(os.listdir(dataset_path))
    logging.info("We will create vector representations for these files:")
    for file in files_list:
        file_path = os.path.join(dataset_path, file)
        if not os.path.isfile(file_path):
            continue
        logging.warning("   %s", file)
        file_content = load_file(file, dataset_path)
        filename = file.split(".")[0]
        collection_count = create_doc_embeddings(document=file_content, file=filename, embeddings=embeddings)
        logging.info("Collection count is %s", collection_count)

    chroma_db.heartbeat()


if __name__ == "__main__":
    main()
