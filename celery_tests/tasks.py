from celery import Celery

app = Celery('tasks', backend='redis://localhost', broker='pyamqp://')

@app.task
def add(x, y):
    return x + y