```shell
curl -X POST \
 -H "Content-Type: application/json"  -H "Authorization: Bearer XXXXXXXXXXXXXXXXXXXXXXXXXXXXX" \
 -d "{\"prompt\": \"How are you\", \"history\": []}"      http://127.0.0.1:8080/api/v1/agent/create-job

```

{"id":"2f8d0c59-6a53-4ed0-848c-9f25fc97f4c2"}


```shell
job_id=$(curl -X POST \
 -H "Content-Type: application/json"  -H "Authorization: Bearer XXXXXXXXXXXXXXXXXXXXXXXXXXXXX" \
 -d '{"prompt": "How are you", "history": []}'      http://127.0.0.1:8080/api/v1/agent/create-job | jq -r ".id")
```

get the status:
```shell
curl -X GET \
 -H "Content-Type: application/json"  -H "Authorization: Bearer XXXXXXXXXXXXXXXXXXXXXXXXXXXXX" \
 http://127.0.0.1:8080/api/v1/agent/get-job-status/$job_id


```