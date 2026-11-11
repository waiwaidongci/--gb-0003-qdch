from starlette.middleware.base import BaseHTTPMiddleware
from uuid import uuid4
class RequestIDMiddleware(BaseHTTPMiddleware):
 async def dispatch(self,request,call_next):
  request.state.request_id=uuid4().hex
  response=await call_next(request);response.headers['X-Request-ID']=request.state.request_id;return response
