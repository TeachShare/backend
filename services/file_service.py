from appwrite.client import Client
from appwrite.services.storage import Storage
from appwrite.input_file import InputFile
from werkzeug.utils import secure_filename
import os

class AppwriteService:
    def __init__(self):
        self.client = Client()
        self.client.set_endpoint('https://sgp.cloud.appwrite.io/v1')
        self.client.set_project(os.getenv("APPWRITE_PROJECT_ID"))
        self.client.set_key(os.getenv("APPWRITE_API_KEY"))

        self.storage = Storage(self.client)
        self.bucket_id = os.getenv("APPWRITE_BUCKET_ID")

    def upload_file(self, file_storage_obj):
        filename = secure_filename(file_storage_obj.filename)
        mime_type = file_storage_obj.content_type

        file_bytes = file_storage_obj.read()

        file_size = len(file_bytes)

        result = self.storage.create_file(
            bucket_id = self.bucket_id,
            file_id = 'unique()',
            file = InputFile.from_bytes(
                file_bytes,
                filename,
                mime_type
            )
        )

        file_id = result.id
        project_id = os.getenv("APPWRITE_PROJECT_ID")
        file_url = f"https://sgp.cloud.appwrite.io/v1/storage/buckets/{self.bucket_id}/files/{file_id}/view?project={project_id}"

        return {
            "url": file_url,
            "name": filename,
            "type": mime_type,
            "size": file_size
        }

    def upload_bytes(self, file_bytes, filename, mime_type):
        file_size = len(file_bytes)

        result = self.storage.create_file(
            bucket_id = self.bucket_id,
            file_id = 'unique()',
            file = InputFile.from_bytes(
                file_bytes,
                filename,
                mime_type
            )
        )

        file_id = result.id
        project_id = os.getenv("APPWRITE_PROJECT_ID")
        file_url = f"https://sgp.cloud.appwrite.io/v1/storage/buckets/{self.bucket_id}/files/{file_id}/view?project={project_id}"

        return {
            "url": file_url,
            "name": filename,
            "type": mime_type,
            "size": file_size
        }