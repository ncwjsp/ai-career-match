#!/bin/sh
set -eu
if [ "$#" -gt 0 ] && [ "$1" != "serve" ]; then
  echo "Expected SageMaker serve command" >&2
  exit 2
fi
exec uvicorn app.nlp.endpoint:app --host 0.0.0.0 --port 8080 --workers 1
