# Next steps

- add docker compose with profiles (dev, production mode)
- add keycloak support
- create a DI for fake auth implementations - i.e. run the service without actual credentials validation
- add database support.for example intercept every request and store some metadata in the table
- create a docker compose setup for:
  - running from IDE, all key dependencies are using a fake implementation
  - E2E development from IDE - main service runs in the IDE, while the key dependencies are running in the containers (service discovery needs to be configurable)
  - E2E development in docker compose - all services run within the same compose stack (service discovery needs to be configurable)