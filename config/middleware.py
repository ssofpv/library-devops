import os
import socket


class InstanceHeaderMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.instance_id = os.getenv("APP_INSTANCE_ID") or socket.gethostname()

    def __call__(self, request):
        response = self.get_response(request)
        response["X-App-Instance"] = self.instance_id
        return response
