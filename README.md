# Recos Backend

## Develop

```
python main.py
celery -A worker.celery worker -l INFO --pool=threads
```
