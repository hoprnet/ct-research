from api_lib.objects.response import APIobject, JsonResponse


@APIobject
class BlokliHealth(JsonResponse):
    health: str


@APIobject
class BlokliSafe(JsonResponse):
    address: str


@APIobject
class BlokliVersion(JsonResponse):
    version: str
