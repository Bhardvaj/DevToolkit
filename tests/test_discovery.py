"""Tests for DiscoveryPipeline."""

from devtoolkit.core.discovery import DiscoveryPipeline
from devtoolkit.core.runner import SafeRunner


def test_discovery_pipeline_methods():
    runner = SafeRunner()
    pipeline = DiscoveryPipeline(runner)

    # Calling discover methods returns Path or None without crashing
    android_sdk = pipeline.discover_android_sdk()
    assert android_sdk is None or android_sdk.exists()

    studio = pipeline.discover_android_studio()
    assert studio is None or studio.exists()

    java_home = pipeline.discover_java_home()
    assert java_home is None or java_home.exists()

    flutter = pipeline.discover_flutter_sdk()
    assert flutter is None or flutter.exists()
