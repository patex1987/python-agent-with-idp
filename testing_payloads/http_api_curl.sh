
# call with basic auth
curl -X POST -H "Content-Type: application/json"  -H "Authorization: Basic Z2Fib3I6eHl6" \
    -d @testing_payloads/game_state.json http://127.0.0.1:8080/api/v1/throttle/calculate_throttle_steps

#headers detected by fastapi ExampleMiddleware: Headers({'host': '127.0.0.1:8080', 'user-agent': 'curl/7.71.1', 'accept': '*/*', 'content-type': 'application/json', 'authorization': 'Basic Z2Fib3I6eHl6', 'content-length': '296'})
#Fastapi validation: Basic auth detected: Z2Fib3I6eHl6
#Fastapi validation: Basic auth creds: username='gabor' password='xyz'
#new throttle step service created 140352828201952
#INFO:     127.0.0.1:55604 - "POST /api/v1/throttle/calculate_throttle_steps HTTP/1.1" 200 OK


# call with bearer token
curl -X POST -H "Content-Type: application/json"  -H "Authorization: Bearer XXXXXXXXXXXXXXXXXXXXXXXXXXXXX" \
    -d @testing_payloads/game_state.json http://127.0.0.1:8080/api/v1/throttle/calculate_throttle_steps

#headers detected by fastapi ExampleMiddleware: Headers({'host': '127.0.0.1:8080', 'user-agent': 'curl/7.71.1', 'accept': '*/*', 'content-type': 'application/json', 'authorization': 'Basic Z2Fib3I6eHl6', 'content-length': '296'})
#Fastapi validation: Basic auth detected: Z2Fib3I6eHl6
#Fastapi validation: Basic auth creds: username='gabor' password='xyz'
#new throttle step service created 140352827527376
#INFO:     127.0.0.1:56108 - "POST /api/v1/throttle/calculate_throttle_steps HTTP/1.1" 200 OK
#headers detected by fastapi ExampleMiddleware: Headers({'host': '127.0.0.1:8080', 'user-agent': 'curl/7.71.1', 'accept': '*/*', 'content-type': 'application/json', 'authorization': 'Bearer XXXXXXXXXXXXXXXXXXXXXXXXXXXXX', 'content-length': '296'})
#Fastapi validation: Bearer auth detected: XXXXXXXXXXXXXXXXXXXXXXXXXXXXX
#Fastapi validation: Bearer auth creds: scheme='Bearer' credentials='XXXXXXXXXXXXXXXXXXXXXXXXXXXXX'