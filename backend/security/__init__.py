"""Security primitives for the paper-only application runtime.

The package intentionally contains no broker credentials and no live-trading
capability.  It provides the boundaries needed to run the local paper service
safely while a production identity provider and secret manager are selected.
"""
