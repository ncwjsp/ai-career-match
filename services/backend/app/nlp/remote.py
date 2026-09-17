"""A-07 NLP sidecar transport; the same SageMaker container also serves embeddings."""

import json

from pydantic import TypeAdapter

from app.core.errors import DependencyUnavailable
from app.core.inference import _build_runtime_client
from app.nlp.entities import MODEL_ID, MODEL_VERSION
from app.nlp.types import PREPROCESSING_VERSION, SKILL_VERSION, NlpAnalysis


class SageMakerNlpProcessor:
    def __init__(self, settings, client=None):
        self.endpoint = settings.sagemaker_embedding_endpoint
        self.client = client or _build_runtime_client(
            settings.sagemaker_region_or_default, settings.sagemaker_timeout_seconds
        )

    def analyze(self, source, language="en"):
        try:
            response = self.client.invoke_endpoint(
                EndpointName=self.endpoint,
                ContentType="application/json",
                Accept="application/json",
                Body=json.dumps({"task": "nlp", "source": source.model_dump(mode="json")}).encode(),
            )
            result = TypeAdapter(NlpAnalysis).validate_python(
                json.loads(response["Body"].read())["analysis"]
            )
            if result.source != source or (
                result.model_id,
                result.model_version,
                result.preprocessing_version,
                result.skill_version,
            ) != (MODEL_ID, MODEL_VERSION, PREPROCESSING_VERSION, SKILL_VERSION):
                raise ValueError("NLP identity drift.")
            return result
        except Exception as error:
            raise DependencyUnavailable(
                "The NLP endpoint is unavailable or incompatible."
            ) from error
