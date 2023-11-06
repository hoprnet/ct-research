import csv
import time

from google.cloud import storage

from .table_entry import TableEntry


class GCPFile:
    def __init__(self, bucketname: str, filename: str):
        self.filename = filename
        self.bucket = GCPBucket(bucketname)

    @property
    def blob(self):
        return self.bucket.blob(self.filename)

    def read(self):
        header, rows = [], []

        with self.blob.open("r") as f:
            reader = csv.reader(f)

            header = next(reader)
            rows = [row for row in reader]

        return header, rows

    def toTableEntry(self):
        header, rows = self.read()

        return [TableEntry.fromList(header, item) for item in rows]

    def __repr__(self):
        return f"GCPFile(in: `{self.bucket.name}`, name: {self.filename})"


class GCPBucket:
    def __init__(self, name: str):
        self.name = name
        self.storage_client = storage.Client()

    def get(self):
        return self.storage_client.bucket(self.name)

    def blob(self, filename: str):
        return self.get().blob(filename)

    def list_blobs(self, folder: str = ""):
        return self.get().list_blobs(prefix=folder)


    def files_in_range(self,start: str, end: str, folder: str = "") -> list[GCPFile]:
        time_format = "%Y%m%d-%H%M%S"
        start, end = time.strptime(start, time_format), time.strptime(end, time_format)

        files: list[GCPFile] = []
        for file in self.list_blobs(folder):
            date_and_time: str = file.name.split("_")[-1].split(".")[0]
            timestamp = time.strptime(date_and_time, "%Y%m%d%H%M%S")

            if timestamp >= start and timestamp < end:
                files.append(GCPFile(self.name, file.name))

        return files
                