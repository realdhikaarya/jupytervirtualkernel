from .kernel_manager import *
from .serializers import *
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView


kernel_manager = KernelManager(timeout=3600)

class PythonCodeRunnerView(APIView):
    def post(self, request, *args, **kwargs):
        user_id = request.data.get("userid", "default_user")
        code = request.data.get("code", "")
        print(f"Received user_id: {user_id}, code: {code}")
        if not code:
            print("No code provided in the request")
            return Response({"error": "No code provided"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = kernel_manager.execute_code(user_id, code)
            #result = asyncio.run(run_kernel(user_id, code))
            print(f"Execution result: {result}")
            return Response({"result": result}, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"Error during code execution: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)