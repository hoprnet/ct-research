from .blokli_provider import BlokliProvider
from .entries import BlokliHealth, BlokliSafe, BlokliVersion


class Version(BlokliProvider[BlokliVersion]):
    query_file: str = "queries/version.graphql"


class Health(BlokliProvider[BlokliHealth]):
    query_file: str = "queries/health.graphql"


class Safes(BlokliProvider[BlokliSafe]):
    query_file: str = "queries/safes.graphql"