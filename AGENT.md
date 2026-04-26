# Agent Development Guidelines

## Security
- Never expose, print, log, or commit secrets.
- Secrets include API keys, passwords, tokens, credentials, `.env` values, private certificates, and internal endpoints.
- Use environment variables or secret managers for sensitive configuration.
- Ensure `.gitignore` excludes sensitive files.
- If secrets are accidentally detected in code, stop and flag them immediately.

---

## Project Architecture
Maintain a clear and modular architecture. At minimum, structure projects as follows:

```bash
project-root/
│
├── ingestion/        # document parsing, preprocessing, chunking, ETL pipelines
├── retrieval/        # embeddings, vector search, reranking, retrieval logic
├── api/              # REST/GraphQL/FastAPI endpoints, service interfaces
├── tests/            # unit, integration, regression tests
│
├── configs/          # configuration files
├── scripts/          # helper scripts
├── docs/             # additional documentation
├── notebooks/        # optional experimentation notebooks
└── README.md