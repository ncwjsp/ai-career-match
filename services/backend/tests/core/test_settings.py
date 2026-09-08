import pytest

from app.core.settings import ConfigurationError, Settings


def test_defaults_need_no_aws_account():
    settings = Settings()
    assert (settings.object_store_backend, settings.embedding_backend) == ("local", "local")
    settings.validate_for_runtime()


def test_production_refuses_mock_adapters():
    with pytest.raises(ConfigurationError, match="Production"):
        Settings(app_env="production").validate_for_runtime()


def test_real_mode_requires_the_shared_cloud_adapters():
    with pytest.raises(ConfigurationError, match="OBJECT_STORE_BACKEND=s3"):
        Settings(app_mode="real").validate_for_runtime()
    with pytest.raises(ConfigurationError, match="EMBEDDING_BACKEND=sagemaker"):
        Settings(
            app_mode="real", object_store_backend="s3", resume_bucket="career-resumes"
        ).validate_for_runtime()


def test_named_cloud_backend_requires_its_target():
    with pytest.raises(ConfigurationError, match="RESUME_BUCKET"):
        Settings(object_store_backend="s3").validate_for_runtime()
    with pytest.raises(ConfigurationError, match="SAGEMAKER_EMBEDDING_ENDPOINT"):
        Settings(embedding_backend="sagemaker").validate_for_runtime()


def test_a_fully_configured_real_deployment_validates():
    Settings(
        app_env="production",
        app_mode="real",
        object_store_backend="s3",
        resume_bucket="career-resumes",
        embedding_backend="sagemaker",
        sagemaker_embedding_endpoint="career-embeddings",
        llm_provider="bedrock",
        llm_model_id="model-id",
    ).validate_for_runtime()


def test_secrets_are_not_printed():
    assert "local_app_only" not in repr(Settings())


def test_import_tokens_are_split_and_trimmed():
    assert Settings(import_access_tokens=" a , b ,, ").import_tokens == frozenset({"a", "b"})


def test_sagemaker_falls_back_to_the_shared_region():
    assert Settings(aws_region="ap-southeast-1").sagemaker_region_or_default == "ap-southeast-1"
    assert Settings(sagemaker_region="us-east-1").sagemaker_region_or_default == "us-east-1"
