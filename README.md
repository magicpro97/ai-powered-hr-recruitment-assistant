# AI-Powered HR Recruitment Assistant

## Purpose

This repository contains the thesis application prototype for creating job descriptions, uploading and screening synthetic CVs, generating interview questions, and using a recruitment-assistant chat. It supports guest and authenticated use.

## Architecture

Docker Compose runs a Next.js frontend, FastAPI backend, PostgreSQL database, embedded Chroma vector store, FreshClam signature updater, and HTTP malware scanner.

## Prerequisites

Install Docker with Docker Compose v2. A valid OpenAI API key and network access are required.

## Quick start

Run the single setup command from the repository root:

```sh
./setup.sh
```

The script accepts `OPENAI_API_KEY` from the environment or prompts without echoing, creates local secrets, starts the stack, and waits for health checks. When ready, open `http://localhost:3000`. To avoid occupied host ports, keep these exports in the same shell for setup and smoke:

```sh
export BACKEND_PORT=18000 FRONTEND_PORT=13000
./setup.sh
./scripts/smoke.sh
```

## Synthetic smoke

After setup completes, exercise the guest upload and screening path with the included fictional fixtures:

```sh
./scripts/smoke.sh
```

## Evidence boundaries

This source snapshot covers the application and its documented local deployment. OpenAI responses are nondeterministic. Evaluation datasets and raw evaluation artifacts are intentionally excluded, so this repository does not independently reproduce reported thesis metrics. Screening output is decision support and requires human review.

## Security and privacy

Use only synthetic data when evaluating this public snapshot. Local runtime data is stored in ignored Docker volumes and paths. Do not commit API keys, applicant records, uploads, or generated logs. Report security concerns through [GitHub Issues](https://github.com/magicpro97/ai-powered-hr-recruitment-assistant/issues).

## Citation

Citation metadata is provided in `CITATION.cff` for release `v1.0.0-thesis`, dated 2026-08-20. The repository is [magicpro97/ai-powered-hr-recruitment-assistant](https://github.com/magicpro97/ai-powered-hr-recruitment-assistant).

## License

Copyright (c) 2026 Ngo The Linh. Released under the MIT License; see `LICENSE`.
