# AIsle (AI Builder Cup Prototype)

This repository contains the prototype for **AIsle** (working title), an AI-powered retail analytics solution built for the Google AI Builder Cup (Retail & Commerce theme).

## The Vision
AIsle transforms physical retail spaces from a data "black box" into a highly measurable environment akin to e-commerce. It moves beyond rudimentary foot traffic counting by leveraging **Google Gemini 1.5 Pro's Multimodal Video Understanding** to extract deep insights on product interaction, dwell time, and conversion outcomes (e.g., "cart abandonment" at the physical shelf).

## Architecture

The solution is built entirely on Google Cloud:

1. **`camera_node/`**: A lightweight local edge script. It simulates a camera feed using the RetailAction dataset, detects motion in predefined interaction zones, and uploads short video clips to GCP.
2. **`backend_service/`**: A serverless Cloud Run / FastAPI service triggered by video uploads. It passes the video to Vertex AI (Gemini 1.5 Pro) with a strict prompt to extract a structured JSON behavioral schema, saving the result to Firestore.
3. **`dashboard/`**: A premium Next.js web application for retail executives to view interaction metrics and query the data using a natural language Gen AI interface.

## Repository Structure

*   `docs/`: Contains the project proposal, architecture plan, and metrics schema.
*   `.agents/`: Contains customized AI agent skills and styling rules for development.
*   `legacy_v1/`: Archived code from earlier iterations of the capstone project.

## Running locally

Backend, from the repository root (settings come from `backend_service/.env`; see `backend_service/.env.example`):

```bash
uv run uvicorn backend_service.main:app --port 8000 --reload
```

`AISLE_DATA_SOURCE` selects where events and clips come from:

*   `firestore` (default): Firestore and Cloud Storage in `GCP_PROJECT_ID`. When they fail, the API answers 503 with the cause and the dashboard shows it. There is no fallback to other data. If the credentials are wrong, startup stops with a clear log line.
*   `seed`: the 17 benchmark events in `backend_service/data/seed_benchmark_events.json`, held in memory, with uploads stored on local disk. Use it to work offline. The tests always run in this mode.

Gemini runs through Vertex AI when `GCP_PROJECT_ID` is a real project, through `GEMINI_API_KEY` otherwise, and in mock mode when neither is set.

Dashboard:

```bash
cd dashboard && npm install && npm run dev
npm run gen:api   # regenerate src/lib/api.gen.ts from the running backend's OpenAPI schema
```

---
*Built for the Google AI Builder Cup.*
