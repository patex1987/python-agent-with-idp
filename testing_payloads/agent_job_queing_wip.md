```shell
curl -X POST \
 -H "Content-Type: application/json"  -H "Authorization: Bearer XXXXXXXXXXXXXXXXXXXXXXXXXXXXX" \
-d "{\"prompt\": \"How are you\", \"history\": []}"      http://127.0.0.1:8080/api/v1/agent/jobs

```

{"id":"2f8d0c59-6a53-4ed0-848c-9f25fc97f4c2"}


```shell
job_id=$(curl -X POST \
 -H "Content-Type: application/json"  -H "Authorization: Bearer XXXXXXXXXXXXXXXXXXXXXXXXXXXXX" \
-d '{"prompt": "How are you", "history": []}'      http://127.0.0.1:8080/api/v1/agent/jobs | jq -r ".id")
```

get the status:
```shell
curl -X GET \
 -H "Content-Type: application/json"  -H "Authorization: Bearer XXXXXXXXXXXXXXXXXXXXXXXXXXXXX" \
 http://127.0.0.1:8080/api/v1/agent/jobs/$job_id


```

request cancellation:
```shell
curl -X POST \
 -H "Content-Type: application/json"  -H "Authorization: Bearer XXXXXXXXXXXXXXXXXXXXXXXXXXXXX" \
 http://127.0.0.1:8080/api/v1/agent/jobs/$job_id/cancel
```

get job events (all):
```shell
curl -X GET \
 -H "Content-Type: application/json"  -H "Authorization: Bearer XXXXXXXXXXXXXXXXXXXXXXXXXXXXX" \
 http://127.0.0.1:8080/api/v1/agent/jobs/$job_id/events
```

get job events (after a sequence cursor):
```shell
after=2
curl -X GET \
 -H "Content-Type: application/json"  -H "Authorization: Bearer XXXXXXXXXXXXXXXXXXXXXXXXXXXXX" \
 "http://127.0.0.1:8080/api/v1/agent/jobs/$job_id/events?after=$after"
```