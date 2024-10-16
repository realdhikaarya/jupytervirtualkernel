import time
import jupyter_client
from threading import Timer
import io
import base64
import matplotlib.pyplot as plt
import queue
from django.core.files.base import ContentFile
import base64
import re
import pandas as pd
from .serializers import *

class KernelManager:
    def __init__(self, timeout=300):
        self.kernels = {}
        self.timeout = timeout
        self.timers = {}

    def start_kernel(self, user_id):
        if user_id not in self.kernels:
            km = jupyter_client.KernelManager(kernel_name='python3')
            km.start_kernel(extra_arguments=['--no-stdout', '--no-stderr'])  # Avoid extra output
            kc = km.client()
            kc.start_channels()
            self.kernels[user_id] = kc
            time.sleep(1)
            print(f"Started kernel for user: {user_id}")
        else:
            print(f"Using existing kernel for user: {user_id}")
        self.reset_inactivity_timer(user_id)
        return self.kernels[user_id]

    def execute_code(self, user_id, code):
        try:
            print(f"Starting kernel for user: {user_id}")
            kc = self.start_kernel(user_id)
            if not kc.is_alive():
                self.start_kernel(user_id)
                print(f"Kernel started for user: {user_id}")
            if kc.shell_channel.is_alive() is False:
                print("Kernel channels are not active. Restarting kernel...")
                kc.stop_channels()
                kc = self.start_kernel(user_id)
            self.wait_for_kernel_to_start(user_id)
            kc.execute(code)
            reply = kc.get_shell_msg(timeout=self.timeout)
            print(f"Shell reply: {reply}")
            result = {
                "status": "ok",
                "execution_count": reply['content']['execution_count'],
                "result": None,
                "output_type": None
            }
            stdout = []
            retries = 3
            while retries > 0:
                try:
                    msg = kc.get_iopub_msg(timeout=3)
                    print(msg)
                    if msg['msg_type'] == 'stream' and msg['content']['name'] == 'stdout':
                        result['result'] = msg['content']['text']
                        result['output_type'] = 'text'
                        result['structured_result'] = self.convert_table_to_dict(result['result'])
                        break
                    elif msg['msg_type'] in ('display_data', 'execute_result'):
                        data = msg['content']['data']
                        if 'image/png' in data:
                            #result['result'] = data['image/png']
                            base64_image = data['image/png']
                            image_url = self.save_image_to_django(base64_image, f"{user_id}_plot.png")
                            result['result'] = image_url
                            result['output_type'] = 'image'
                        elif 'text/html' in data:
                            result['result'] = data['text/html']
                            result['output_type'] = 'html'
                        elif 'text/plain' in data:
                            result['result'] = data['text/plain']
                            result['output_type'] = 'text'
                        break
                    elif msg['msg_type'] == 'error':
                        return {
                            "status": "error",
                            "error": msg['content']['evalue']
                        }
                except queue.Empty:
                    retries -= 1
                    print("Queue is empty")
                    if retries == 0:
                        break
            return result
        except Exception as e:
            print(f"Kernel execution failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
        
    def reset_inactivity_timer(self, user_id):
        if user_id in self.timers:
            self.timers[user_id].cancel()
        self.timers[user_id] = Timer(self.timeout, self.shutdown_kernel, [user_id])
        self.timers[user_id].start()
        print(f"Reset inactivity timer for user: {user_id}")

    def shutdown_kernel(self, user_id):
        if user_id in self.kernels:
            print(f"Shutting down kernel for user {user_id} due to inactivity.")
            self.kernels[user_id].shutdown()
            del self.kernels[user_id]
            del self.timers[user_id]
            print(f"Kernel for user {user_id} has been shut down.")

    def wait_for_kernel_to_start(self, user_id):
        kc = self.kernels.get(user_id)
        if kc is None:
            raise Exception(f"No kernel found for user: {user_id}")
        while not (kc.shell_channel.is_alive() and kc.is_alive()):
            print("Waiting for kernel to be ready...")
            time.sleep(0.5)
        print(f"Kernel for user {user_id} is ready!")

    def save_image_to_django(self, base64_image, filename):
        image_data = base64.b64decode(base64_image)
        image_file = ContentFile(image_data, name=filename)
        image_serializer = ImageSerializer(data={'image': image_file})
        if image_serializer.is_valid():
            image_instance = image_serializer.save()
            print(image_instance)
            return image_instance.image.url
        else:
            print(f"Image serialization failed: {image_serializer.errors}")
            return None

    def convert_table_to_dict(self, result_text):
        try:
            lines = result_text.strip().split('\n')
            header = lines[0].split()
            data_rows = []
            row_pattern = re.compile(r'(\w+)\s+(\d+)')
            for line in lines[1:]:
                match = row_pattern.match(line.strip())
                if match:
                    data_rows.append(match.groups())
            if data_rows:
                df = pd.DataFrame(data_rows, columns=header)
                return df.to_dict(orient='records') 
            else:
                return None
        except Exception as e:
            print(f"Failed to convert table to dict: {str(e)}")
            return None