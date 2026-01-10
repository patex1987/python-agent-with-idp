```shell
curl -X POST \
 -H "Content-Type: application/json"  -H "Authorization: Bearer XXXXXXXXXXXXXXXXXXXXXXXXXXXXX" \
-d "{\"prompt\": \"How are you\", \"history\": []}"      http://127.0.0.1:8080/api/v1/agent/runs

```

{"id":"2f8d0c59-6a53-4ed0-848c-9f25fc97f4c2"}


```shell
run_id=$(curl -X POST \
 -H "Content-Type: application/json"  -H "Authorization: Bearer XXXXXXXXXXXXXXXXXXXXXXXXXXXXX" \
-d '{"prompt": "How are you", "history": []}'      http://127.0.0.1:8080/api/v1/agent/runs | jq -r ".id")
```

get the status:
```shell
curl -X GET \
 -H "Content-Type: application/json"  -H "Authorization: Bearer XXXXXXXXXXXXXXXXXXXXXXXXXXXXX" \
 http://127.0.0.1:8080/api/v1/agent/runs/$run_id


```

request cancellation:
```shell
curl -X POST \
 -H "Content-Type: application/json"  -H "Authorization: Bearer XXXXXXXXXXXXXXXXXXXXXXXXXXXXX" \
 http://127.0.0.1:8080/api/v1/agent/runs/$run_id/cancel
```

get job events (all):
```shell
curl -X GET \
 -H "Content-Type: application/json"  -H "Authorization: Bearer XXXXXXXXXXXXXXXXXXXXXXXXXXXXX" \
 http://127.0.0.1:8080/api/v1/agent/runs/$run_id/events
```

get job events (after a sequence cursor):
```shell
after=2
curl -X GET \
 -H "Content-Type: application/json"  -H "Authorization: Bearer XXXXXXXXXXXXXXXXXXXXXXXXXXXXX" \
 "http://127.0.0.1:8080/api/v1/agent/runs/$run_id/events?after=$after"
```