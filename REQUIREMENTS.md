# REQUIREMENTS

## Functional requirements

### Authentication

- users can create/login to an account
- authenticated users can access only authorized tenants

### Multi-tenancy

- tenant is the primary isolation boundary
- tenant-owned data must be isolated
- memberships and roles are enforced

### Platform connections

- seller can connect supported Meta assets through official authorization
- seller can see connection state
- seller can disconnect/revoke according to supported platform behavior
- credentials are not exposed to frontend clients unnecessarily

### Messaging

- incoming platform events are accepted through a verified webhook
- events are persisted
- duplicate events are idempotent
- platform messages are normalized

### AI extraction

- order candidates can be extracted from messages
- missing fields remain missing
- uncertain values are flagged
- extraction output follows a strict schema
- AI cannot directly authorize irreversible actions

### Orders

- order candidate can be reviewed
- seller can edit/confirm
- order state transitions are controlled
- order history is auditable

### Export

- confirmed orders can be exported
- Unicode and special characters are preserved

## Non-functional requirements

- tenant isolation
- secure secret handling
- structured logs
- deterministic validation
- idempotent event processing
- observable failures
- testability
- maintainability
- explicit external-integration evidence
