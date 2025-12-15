# Service

## Health checks
Periodically executing a check against a dummy endpoint (you can define more advanced checks)
```json
{"event": "new request id has been created", "timestamp": "2025-09-08T17:11:06.045360Z", "service_name": "throttling_sequencer_fastapi", "version": "0.1", "level": "info"}
INFO:     127.0.0.1:44232 - "GET /api/v1/health/dummy-health HTTP/1.1" 200 OK
```

# Development

## Running from IDE
To run in development mode in pycharm (or your preferred IDE) use: `[./configuration/local_or_ide/local_development.env](../configuration/local_or_ide/local_development.env)`
and execute `throttling_sequencer_fastapi/manage.py` with that env file

## Running from docker
To run in development mode once the container the image is built (see the sections below), run

To execute the service immediately:
```shell
docker run -it -p 8080:8080 \
  --env-file "/home/patex1987/development/throttling_sequencer_webapp/configuration/docker/local_development.env"  \
  --rm \
  fastapi_rest:local_dev
```

Output:
```text
{"event": "Uvicorn server configuration: host='0.0.0.0' port=8080 log_level='info' reload=True log_config_path='/app/throttling_sequencer/configuration/log_config_json.json'", "timestamp": "2025-09-09T15:41:58.886552Z", "service_name": "throttling_sequencer_fastapi", "version": "0.1", "level": "info"}
{"event": "Will watch for changes in these directories: ['/app']", "timestamp": "2025-09-09T15:41:58.887500Z", "service_name": "throttling_sequencer_fastapi", "version": "0.1", "level": "info"}
{"event": "Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)", "timestamp": "2025-09-09T15:41:58.887729Z", "service_name": "throttling_sequencer_fastapi", "version": "0.1", "level": "info"}
{"event": "Started reloader process [7] using StatReload", "timestamp": "2025-09-09T15:41:58.887852Z", "service_name": "throttling_sequencer_fastapi", "version": "0.1", "level": "info"}
{"event": "Started server process [9]", "timestamp": "2025-09-09T15:42:00.231746Z", "service_name": "throttling_sequencer_fastapi", "version": "0.1", "level": "info"}
{"event": "Waiting for application startup.", "timestamp": "2025-09-09T15:42:00.231913Z", "service_name": "throttling_sequencer_fastapi", "version": "0.1", "level": "info"}
```

To execute the container with a shell session:
```shell
docker run -it -p 8080:8080 \
  --env-file "/home/patex1987/development/throttling_sequencer_webapp/configuration/docker/local_development.env"  \
  --rm \
  fastapi_rest:local_dev \
  /bin/bash
```

If you don't want to use the env vars, and run uvicorn directly and configure through cli args, check the Dockerfile for the commented out commands
```dockerfile
# ---------- dev (editable install) ----------
#CMD ["uvicorn","throttling_sequencer.app:create_app","--host","0.0.0.0","--port","8080","--reload","--log-config","./throttling_sequencer/configuration/log_config_json.json","--factory"]
CMD ["python", "manage.py"]

# ---------- prod (lean runtime) ----------
# ...
#CMD ["uvicorn","throttling_sequencer.app:create_app","--host","0.0.0.0","--port","8080","--log-config","./throttling_sequencer/configuration/log_config_json.json","--factory"]
CMD ["python", "manage.py"]
```


### Build in development mode

1. Navigate to the `throttling_sequencer_fastapi` folder
2. Execute:
```shell
docker build --target dev -t fastapi_rest:local_dev -f ./Dockerfile .
```

enter the container with non-running service:
```shell
docker run -it --rm fastapi_rest:local_dev /bin/bash 
```

### Build in production mode
1. Navigate to the `throttling_sequencer_fastapi` folder
2. Execute:
```shell
docker build --target prod -t fastapi_rest:local_prod -f ./Dockerfile .
```
