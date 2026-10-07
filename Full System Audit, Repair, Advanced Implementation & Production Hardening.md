# MASTER CURSOR ENGINEERING PROMPT
## Autonomous System — Full Codebase Audit, Repair, Deep Implementation & Production-Grade Hardening

You are acting as a **Principal Software Architect + Staff/Principal Backend Engineer + AI Systems Engineer + Distributed Systems Engineer + DevOps/SRE Engineer + Security Engineer + QA Automation Engineer**.

Your task is NOT to merely modify UI, silence errors, hardcode responses, mock functionality, or make the application appear functional.

Your task is to take the **entire existing codebase** and transform it into a **real, deeply engineered, production-grade, scalable, fault-tolerant, observable, secure, autonomous system** in which every implemented feature and sub-feature actually works end-to-end.

The objective is:

> **Audit → Understand → Architect → Repair → Implement → Integrate → Test → Stress Test → Harden → Verify → Document**

Do not stop at identifying problems.

**Find the problems and actually fix them.**

---

# 1. PRIMARY OBJECTIVE

Perform a complete engineering audit of the current repository.

Identify and eliminate:

- broken functionality
- incomplete functionality
- placeholder implementations
- mocked APIs
- fake success responses
- hardcoded data
- static dashboards pretending to represent live data
- TODO implementations
- dead code
- unreachable code
- incorrect business logic
- incomplete algorithms
- missing API endpoints
- broken API endpoints
- incorrect API contracts
- inconsistent request/response schemas
- missing validation
- weak error handling
- race conditions
- duplicate execution
- duplicate records
- non-idempotent jobs
- missing retry mechanisms
- incorrect retry mechanisms
- missing transactions
- inconsistent database state
- stale state
- missing indexes
- inefficient queries
- N+1 queries
- memory leaks
- resource leaks
- authentication weaknesses
- authorization bypasses
- tenant isolation failures
- secret exposure
- insecure environment handling
- missing audit logs
- missing observability
- missing metrics
- missing tracing
- missing health checks
- background jobs that are not durable
- workers that silently fail
- queues that can lose jobs
- cron jobs that duplicate execution
- AI agents without guardrails
- agents that hallucinate business facts
- tools that can execute without authorization
- integrations that are only partially implemented
- missing fallback providers
- missing circuit breakers
- incorrect state machines
- invalid edge-case handling
- missing rate limits
- missing quota management
- missing cost controls
- missing compliance controls
- broken frontend/backend contracts
- broken realtime functionality
- incorrect WebSocket lifecycle handling
- incorrect webhook handling
- missing webhook signature verification
- missing replay protection
- missing event deduplication
- missing concurrency controls
- missing rollback mechanisms
- missing feature flags
- incomplete configuration management
- incomplete production deployment configuration
- insufficient test coverage
- tests that pass while functionality is actually broken

and anything else that prevents the platform from being genuinely production-ready.

---

# 2. ABSOLUTE RULE: NO FAKE IMPLEMENTATION

DO NOT solve problems using:

- hardcoded arrays
- hardcoded JSON responses
- fake database responses
- simulated API responses
- fake success messages
- arbitrary `setTimeout()` pretending to perform work
- random numbers pretending to be analytics
- placeholder AI responses
- static dashboard metrics
- fake workflow state
- mocked services in production code
- frontend-only validation
- localStorage pretending to be a backend
- hardcoded status values
- "TODO" comments as implementation
- commented-out functionality
- disabled error handling
- swallowing exceptions
- returning `200 OK` for failed operations
- returning success when an operation has not actually completed

Mocks are acceptable ONLY inside isolated automated tests.

Production functionality must use:

**real persistence + real business logic + real APIs/integrations + real workflows + real validation + real error handling.**

If an external provider cannot currently be connected because credentials are unavailable:

1. implement the complete provider abstraction;
2. implement the real integration contract;
3. validate configuration at runtime;
4. provide a deterministic failure state;
5. expose the exact configuration requirement;
6. never pretend the operation succeeded.

---

# 3. FIRST TASK — DEEPLY UNDERSTAND THE ENTIRE REPOSITORY

Before making major changes, inspect the repository comprehensively.

Analyze:

- directory structure
- package manager
- monorepo structure
- applications
- packages
- backend
- frontend
- workers
- services
- database
- migrations
- API routes
- server actions
- RPC endpoints
- WebSockets
- queues
- schedulers
- cron jobs
- authentication
- authorization
- middleware
- environment configuration
- third-party integrations
- AI providers
- storage
- caching
- observability
- tests
- CI/CD
- Docker
- deployment configuration
- documentation

Do not assume that a file named correctly is implemented correctly.

Trace functionality from:

**UI → API → service → business logic → database → external provider → event → worker → final state → UI**

for every major feature.

---

# 4. BUILD A REAL SYSTEM INVENTORY

Create an internal implementation matrix.

For every feature, sub-feature, endpoint, worker, agent, service and integration determine:

| Component | Exists | Functional | Real Data | Tested | Production Ready | Missing |
|---|---:|---:|---:|---:|---:|---|
| Feature | ✓/✗ | ✓/✗ | ✓/✗ | ✓/✗ | ✓/✗ | Details |

Classify every item as:

- COMPLETE
- PARTIALLY COMPLETE
- BROKEN
- MOCKED
- PLACEHOLDER
- MISSING
- INSECURE
- NON-SCALABLE
- PERFORMANCE RISK
- PRODUCTION READY

Do not declare a component complete merely because it compiles.

---

# 5. ARCHITECTURAL REQUIREMENT

Do not patch the application randomly.

Before implementing major structural changes, establish the correct architecture.

The architecture must support:

- modular services
- clear domain boundaries
- typed contracts
- durable workflows
- asynchronous processing
- event-driven execution where appropriate
- idempotent operations
- transactional consistency
- horizontal scaling
- tenant isolation
- provider abstraction
- observability
- fault tolerance
- retries
- dead-letter handling
- circuit breakers
- rate limiting
- quota management
- cost controls
- security boundaries
- auditability
- versioned AI agents
- versioned prompts
- versioned business rules
- reproducibility
- rollback
- disaster recovery

Avoid unnecessary microservices.

Use a **modular monolith where appropriate**, but design domain boundaries so components can be extracted into independent services later.

---

# 6. REAL BUSINESS LOGIC

Every feature must have an actual algorithmic implementation.

For every major process define:

### Input
What enters the system?

### Validation
What must be true?

### State
What state does the entity currently have?

### Decision
What algorithm determines the next action?

### Execution
What actual operation occurs?

### Persistence
What state is saved?

### Event
What event is emitted?

### Retry
What happens if execution fails?

### Compensation
What happens if the next step fails?

### Observability
How is execution measured?

### Recovery
How does the system resume after interruption?

### Idempotency
How is duplicate execution prevented?

### Security
Who is allowed to execute the operation?

Do this systematically.

---

# 7. STATE MACHINES

Where workflows exist, do NOT rely on arbitrary booleans.

Implement explicit state machines.

Example:

```text
DISCOVERED
    ↓
QUALIFIED
    ↓
RESEARCHED
    ↓
READY
    ↓
PROCESSING
    ↓
VALIDATED
    ↓
EXECUTING
    ↓
COMPLETED
```

with explicit failure states:

```text
RETRYABLE_FAILURE
PERMANENT_FAILURE
BLOCKED
ESCALATED
CANCELLED
DEAD_LETTER
```

Invalid state transitions must be rejected.

State transitions must be atomic and auditable.

---

# 8. DURABLE WORKFLOWS

Any process that may run for:

- seconds
- minutes
- hours
- days
- weeks

must not depend on an in-memory process staying alive.

Implement durable workflow execution using the project's appropriate workflow technology.

The system must survive:

- server restart
- worker restart
- deployment
- network interruption
- API timeout
- provider outage
- duplicate webhook
- process crash
- temporary database failure

When a process restarts, it must resume safely.

---

# 9. IDEMPOTENCY

Every externally visible operation must have an idempotency strategy.

Examples:

```text
workflow_id
run_id
job_id
event_id
request_id
provider_operation_id
idempotency_key
```

A retry must NEVER accidentally:

- create duplicate leads
- send duplicate messages
- upload duplicate videos
- create duplicate payments
- create duplicate proposals
- create duplicate calendar events
- create duplicate database records
- execute the same expensive operation twice

Implement database-level uniqueness constraints where appropriate.

Application-level checks alone are insufficient.

---

# 10. DATABASE ENGINEERING

Audit the database deeply.

Check:

- schema correctness
- normalization
- denormalization where justified
- indexes
- composite indexes
- unique constraints
- foreign keys
- cascading rules
- transactions
- optimistic locking
- pessimistic locking where appropriate
- connection pooling
- query plans
- pagination
- cursor pagination
- soft deletion
- audit history
- versioning
- event storage
- retention policies

Find and fix:

- N+1 queries
- full-table scans
- unbounded queries
- missing indexes
- inconsistent transactions
- race conditions
- orphaned records
- duplicate records
- unsafe migrations

Never solve database problems by simply caching everything.

---

# 11. API ENGINEERING

Audit EVERY API endpoint.

For each endpoint verify:

- authentication
- authorization
- tenant ownership
- input validation
- schema validation
- output schema
- HTTP semantics
- error semantics
- rate limits
- idempotency
- pagination
- filtering
- sorting
- timeout
- cancellation
- logging
- tracing
- metrics
- audit event
- database consistency
- external API handling

Implement strong API contracts.

Every endpoint must have predictable responses.

Use appropriate status codes.

Never expose:

- stack traces
- secrets
- provider credentials
- internal database details
- sensitive tenant information

---

# 12. API ERROR MODEL

Create a centralized error model.

For example:

```text
VALIDATION_ERROR
AUTHENTICATION_ERROR
AUTHORIZATION_ERROR
NOT_FOUND
CONFLICT
RATE_LIMITED
QUOTA_EXCEEDED
PROVIDER_ERROR
TIMEOUT
TEMPORARY_FAILURE
PERMANENT_FAILURE
POLICY_BLOCKED
ESCALATION_REQUIRED
INTERNAL_ERROR
```

Errors must be:

- machine-readable
- human-readable
- traceable
- logged
- correlated to request IDs

---

# 13. RETRY ARCHITECTURE

Do not retry everything.

Classify errors:

### Retryable

- network timeout
- temporary provider failure
- rate limit
- transient database failure

### Non-retryable

- invalid credentials
- invalid request
- policy violation
- malformed data
- authorization failure

Implement:

- exponential backoff
- jitter
- maximum attempts
- retry budget
- dead-letter queue
- retry metadata
- provider-aware retry policy

Prevent retry storms.

---

# 14. CIRCUIT BREAKERS

External providers must have circuit-breaker protection.

For each provider track:

- success rate
- latency
- timeout rate
- error rate
- quota
- cost
- availability

States:

```text
CLOSED
OPEN
HALF_OPEN
```

When a provider becomes unhealthy:

1. stop sending unnecessary requests;
2. route to fallback if available;
3. preserve workflow state;
4. retry later;
5. alert only when recovery cannot occur automatically.

---

# 15. PROVIDER ABSTRACTION

Do not tightly couple the entire system to one external provider.

Create interfaces such as:

```text
LLMProvider
TTSProvider
ImageProvider
EmailProvider
CRMProvider
CalendarProvider
PaymentProvider
ESignProvider
DataProvider
StorageProvider
NotificationProvider
```

Implement provider adapters.

This allows:

- provider switching
- failover
- A/B evaluation
- regional providers
- cost optimization
- model routing

---

# 16. AI/AGENT ARCHITECTURE

AI must NOT be allowed to directly perform uncontrolled side effects.

Implement:

```text
Agent
 ↓
Planner/Decision
 ↓
Tool Selection
 ↓
Policy Guard
 ↓
Validation
 ↓
Tool Execution
 ↓
Result Validation
 ↓
Persistence
 ↓
Event
```

Agents must operate under explicit permissions.

Example:

```text
READ_PROFILE
READ_LEAD
RESEARCH
DRAFT_MESSAGE
SEND_MESSAGE
CREATE_PROPOSAL
CREATE_PAYMENT
MODIFY_METADATA
PUBLISH
```

A low-privilege agent must never inherit high-privilege capabilities.

---

# 17. AI OUTPUT VALIDATION

Never trust raw LLM output.

Every structured AI output must pass:

1. schema validation
2. business-rule validation
3. factual grounding
4. policy validation
5. permission validation
6. confidence threshold
7. safety validation

If validation fails:

```text
RETRY → REPAIR → SECOND VALIDATION → ESCALATE/REJECT
```

Never directly execute arbitrary model output.

---

# 18. AI VERSIONING

Persist:

- agent ID
- agent version
- model
- model version
- prompt version
- tool version
- policy version
- input references
- output
- critic result
- confidence
- timestamp

Every AI decision must be reproducible as far as the underlying provider permits.

---

# 19. MEMORY AND KNOWLEDGE

If the system uses AI memory/RAG:

Implement proper separation between:

```text
Source Documents
Knowledge Chunks
Embeddings
Metadata
Claims
Evidence
Agent Context
Conversation Memory
Long-Term Business Memory
```

Do not allow arbitrary conversation text to silently become trusted business knowledge.

Use:

- source attribution
- confidence
- freshness
- versioning
- tenant isolation
- deletion propagation

---

# 20. LEARNING SYSTEM

Do not create fake "self-learning" dashboards.

If the PRD defines learning loops, implement actual learning mechanisms.

Capture:

```text
input
decision
variant
action
result
outcome
cost
latency
conversion
failure
```

Then use real statistical mechanisms where appropriate.

Examples:

- Bayesian updating
- Thompson Sampling
- contextual bandits
- weighted scoring
- calibration
- regression
- ranking models
- anomaly detection
- cohort analysis
- experiment analysis

Do not use AI merely to generate a narrative claiming the system learned.

---

# 21. EXPERIMENT ENGINE

Implement real experimentation.

Every experiment must have:

```text
experiment_id
hypothesis
control
variants
population
allocation
start_time
end_time
primary_metric
secondary_metrics
minimum_sample
confidence criteria
winner
rollback
```

Never change multiple variables simultaneously when causal attribution matters.

Store experiment history permanently.

---

# 22. AUTONOMOUS YOUTUBE ENGINE REQUIREMENTS

Where the repository implements the YouTube engine, preserve and fully implement the PRD architecture:

- Setup/Credential Vault
- Niche Scout
- Competitor Analyst
- Topic Planner
- Research & Fact Engine
- Script Writer
- Originality & Quality Gate
- Voice
- Visuals & Editing
- Title & Thumbnail
- Publisher
- Analytics Collector
- Diagnostician/Optimizer
- Orchestrator/Exception Queue

These modules must be real services/components rather than UI labels.

The PRD requires source-backed research, originality checking, production, publishing, analytics, diagnostics and optimization.

Implement the complete lifecycle:

```text
NICHE
→ COMPETITOR RESEARCH
→ TOPIC DISCOVERY
→ RESEARCH
→ CLAIM EXTRACTION
→ FACT VERIFICATION
→ SCRIPT
→ ORIGINALITY CHECK
→ QUALITY GATE
→ VOICE
→ VISUALS
→ RENDER
→ PACKAGING
→ POLICY CHECK
→ PUBLISH
→ ANALYTICS
→ DIAGNOSIS
→ OPTIMIZATION
→ LEARNING
```

No stage may simply pretend to complete.

---

# 23. YOUTUBE COMPLIANCE

Implement hard safety boundaries.

The system must NOT:

- fake engagement
- buy views
- buy subscribers
- scrape/reupload videos
- clone real people
- clone real voices
- bypass API restrictions
- bypass quota
- circumvent platform controls

The PRD explicitly defines these as hard rules.

Implement:

- quota budgeter
- upload idempotency
- synthetic-media declaration
- Made-for-Kids declaration
- originality gate
- copyright asset records
- asset licensing records
- kill switch
- policy escalation
- complete audit trail

---

# 24. YOUTUBE OPTIMIZATION ENGINE

Implement real funnel diagnosis:

```text
Impressions
   ↓
CTR
   ↓
Watch
   ↓
Retention
   ↓
Session continuation
   ↓
Return viewer
   ↓
Subscriber
```

Diagnosis must determine which stage failed before changing anything.

Use controlled changes.

Store:

```text
before_metrics
change
timestamp
after_metrics
effect
decision
rollback
```

The PRD specifically requires one change at a time, fixed evaluation windows, rollback and cross-video learning.

---

# 25. AUTONOMOUS LEAD-TO-CLIENT ENGINE

Where the repository implements the acquisition engine, fully implement:

```text
Service Profile
→ ICP Research
→ Lead Sourcing
→ Enrichment
→ Verification
→ Lead Scoring
→ Personalisation
→ Outreach
→ Reply Classification
→ Qualification
→ Objection Handling
→ Booking/Proposal/Payment
→ Conversion
→ Human Handoff
→ Learning
```

The PRD requires a shared cross-channel state so a prospect cannot accidentally receive duplicate or conflicting outreach.

Implement the complete state machine.

---

# 26. LEAD SCORING

Do not hardcode:

```text
score = 80
```

Implement a real scoring pipeline based on:

```text
FIT
×
INTENT
×
REACHABILITY
```

with:

- configurable weights
- normalization
- confidence
- freshness
- source reliability
- historical outcomes

Where enough data exists, implement outcome-based retraining.

---

# 27. MULTI-ARMED BANDIT

Where ICP experimentation exists, implement a genuine bandit mechanism.

Support:

- exploration
- exploitation
- posterior updates
- sample size
- confidence
- budget allocation
- cold-start handling
- minimum exploration
- winner promotion
- rollback

Do not randomly allocate traffic and call it a bandit.

---

# 28. LEAD DEDUPLICATION

Implement deterministic + probabilistic deduplication.

Use:

```text
email
phone
company domain
company ID
normalized name
provider IDs
```

and fuzzy/entity matching where appropriate.

Prevent duplicate outreach.

---

# 29. CONSENT AND SUPPRESSION

Implement a centralized suppression engine.

Before EVERY outbound action:

```text
Identity
→ Tenant
→ Channel
→ Consent
→ Suppression
→ Policy
→ Rate Limit
→ Reputation
→ Budget
→ Send
```

Never bypass this pipeline.

---

# 30. OUTREACH POLICY ENGINE

No channel may send directly.

All outbound communication must pass:

```text
Draft
→ Fact Check
→ Compliance Check
→ Consent Check
→ Suppression Check
→ Policy Guard
→ Rate Limit
→ Send
```

The Lead-to-Client PRD specifically requires the policy guard to mediate agent actions and requires consent-gated WhatsApp/SMS/voice behavior.

---

# 31. CONVERSATION ENGINE

Implement a real conversational state machine.

Classify:

- interested
- question
- objection
- not now
- referral
- wrong person
- unsubscribe
- OOO
- hostile
- legal
- complaint
- qualified
- disqualified
- conversion-ready

Maintain:

```text
conversation_state
intent
confidence
next_action
last_action
next_action_at
channel
owner_agent
```

The conversation must never lose context when moving between channels.

---

# 32. PROPOSAL / PAYMENT / BOOKING

These must use real integrations.

Implement:

```text
proposal draft
→ validation
→ approval rules
→ e-sign
→ signed state
→ payment
→ payment webhook
→ verified payment
→ conversion
```

Never treat a frontend success page as proof of payment.

Verify provider webhooks cryptographically.

Use idempotency for payment events.

---

# 33. WEBHOOK ENGINE

Every webhook must support:

- signature verification
- timestamp validation
- replay protection
- event ID deduplication
- schema validation
- transaction boundary
- async processing
- retry handling
- dead-letter handling
- provider response acknowledgement

---

# 34. TENANT ISOLATION

If the product is multi-tenant:

EVERY tenant-scoped query must enforce tenant boundaries.

Never trust:

```text
tenant_id
```

coming directly from an untrusted client.

Resolve tenant identity from authenticated context.

Implement:

- tenant-aware repositories
- authorization middleware
- database-level safeguards where possible
- cross-tenant integration isolation
- per-tenant secrets
- per-tenant quotas
- per-tenant budgets
- per-tenant kill switches

The PRD explicitly requires tenant isolation so one bad tenant cannot affect another tenant's deliverability.

---

# 35. SECURITY AUDIT

Perform a serious security review.

Check for:

- OWASP Top 10
- broken access control
- IDOR
- SSRF
- injection
- XSS
- CSRF
- insecure deserialization
- command injection
- path traversal
- secret leakage
- JWT weaknesses
- session vulnerabilities
- webhook spoofing
- privilege escalation
- insecure file uploads
- malicious prompts
- prompt injection
- tool injection
- data exfiltration

AI-specific security must include:

```text
Prompt Injection Defense
Tool Permission Boundaries
Untrusted Content Isolation
Data Exfiltration Prevention
Output Validation
Secret Redaction
Cross-Tenant Context Isolation
```

---

# 36. COST ENGINE

Every expensive operation must be measurable.

Track:

```text
provider
model
tokens
request count
latency
cost
tenant
workflow
feature
agent
```

Implement:

- daily budget
- monthly budget
- per-tenant budget
- per-workflow budget
- per-provider budget
- emergency kill switch
- model routing
- cheap-model classification
- expensive-model escalation

Never allow an infinite AI loop.

---

# 37. OBSERVABILITY

Implement production observability.

Every request/job/workflow should have:

```text
trace_id
request_id
tenant_id
workflow_id
job_id
agent_id
version
```

Collect:

### Logs

Structured JSON logs.

### Metrics

- throughput
- latency
- errors
- retries
- queue depth
- provider health
- token usage
- cost
- conversion
- success rate

### Traces

Trace:

```text
UI
→ API
→ Service
→ DB
→ Queue
→ Worker
→ AI provider
→ External API
```

---

# 38. HEALTH SYSTEM

Implement:

```text
/health
/ready
/live
```

and deeper dependency checks.

Distinguish:

```text
Liveness
Readiness
Dependency Health
Degraded Mode
```

Do not report the application healthy when critical dependencies are unavailable.

---

# 39. REAL-TIME SYSTEMS

If WebSockets/realtime features exist, audit:

- connection lifecycle
- authentication
- reconnect
- heartbeat
- timeout
- backpressure
- duplicate events
- ordering
- missed events
- reconnection state recovery
- authorization
- graceful shutdown

Implement event sequence IDs where required.

---

# 40. FILE / MEDIA PROCESSING

For media generation or document processing:

- validate MIME types
- validate file signatures
- enforce size limits
- use isolated processing
- sanitize filenames
- track processing state
- store metadata
- use object storage
- checksum files
- prevent duplicate processing
- handle partial uploads
- retry failed processing

---

# 41. FRONTEND AUDIT

Audit every page and component.

Every button must either:

- perform a real action;
- navigate to a real implementation;
- open a real workflow;
- or be intentionally disabled with a clear reason.

No dead buttons.

No fake loading states.

No fake success notifications.

No UI state that diverges from backend truth.

Implement:

- optimistic updates only where safe
- server reconciliation
- error boundaries
- loading states
- empty states
- retry states
- permission states
- offline/degraded states

---

# 42. DASHBOARDS

Every metric displayed must originate from real data.

Trace:

```text
Dashboard Metric
→ Query
→ Database/Event Store
→ Calculation
→ API
→ UI
```

Do not fabricate metrics.

Do not hardcode charts.

Do not show "100%" because no backend data exists.

If there is insufficient data, show:

```text
No data available
```

rather than invented numbers.

---

# 43. AUTOMATION ENGINE

All automation must be deterministic and recoverable.

Implement:

- scheduler
- job queue
- worker
- job state
- retry
- dead-letter
- cancellation
- timeout
- concurrency
- priority
- dependency
- workflow resume

Example:

```text
SCHEDULED
→ QUEUED
→ RUNNING
→ VALIDATING
→ COMPLETED
```

Failure:

```text
RUNNING
→ RETRY_PENDING
→ RETRYING
→ FAILED
→ DEAD_LETTER
```

---

# 44. CONCURRENCY

Explicitly identify race conditions.

Protect:

- financial operations
- outbound sends
- workflow transitions
- lead ownership
- resource allocation
- quotas
- inventory-like resources
- provider calls
- experiment allocation

Use:

- optimistic locking
- atomic DB updates
- distributed locks
- unique constraints
- transactional outbox
- idempotency

where appropriate.

---

# 45. EVENT ARCHITECTURE

Implement an append-only event model for important business actions.

Example:

```text
LeadCreated
LeadQualified
ResearchCompleted
MessageDrafted
MessageApproved
MessageSent
ReplyReceived
LeadQualified
MeetingBooked
ProposalCreated
ProposalSigned
PaymentReceived
ClientConverted
```

Events should contain:

```text
event_id
aggregate_id
tenant_id
event_type
actor
version
payload
timestamp
correlation_id
```

Do not mutate historical events.

---

# 46. TRANSACTIONAL OUTBOX

Where database state and event publication must remain consistent:

Implement the transactional outbox pattern.

Example:

```text
DB Transaction
    ├── Update entity
    └── Insert outbox event

Commit

Outbox Worker
    ↓
Publish Event
    ↓
Mark Published
```

This prevents lost events.

---

# 47. CACHE STRATEGY

Audit all caching.

For every cache determine:

- TTL
- invalidation
- consistency requirement
- stale tolerance
- namespace
- tenant isolation
- memory limit

Never use caching to hide incorrect database logic.

---

# 48. RATE LIMITING

Implement rate limiting at:

- user
- tenant
- IP
- endpoint
- provider
- mailbox
- channel
- workflow

Use distributed rate limiting when horizontally scaled.

---

# 49. QUOTA MANAGEMENT

For APIs with quotas:

Track:

```text
quota_limit
quota_used
quota_remaining
quota_reset
reserved_quota
estimated_cost
```

Reserve quota before expensive operations.

Prevent one workflow from consuming the entire platform quota.

---

# 50. TESTING REQUIREMENT

Do not merely run the existing tests.

Build a complete test pyramid.

### Unit tests

Business logic.

### Integration tests

Database + services.

### Contract tests

API/provider contracts.

### Workflow tests

Long-running processes.

### End-to-end tests

Real user journeys.

### Failure tests

Provider failures.

### Security tests

Authorization and injection.

### Load tests

Concurrency and throughput.

### Regression tests

Previously broken bugs.

---

# 51. TEST EVERY FEATURE END-TO-END

For every major feature produce:

```text
Happy path
Validation failure
Authentication failure
Authorization failure
Duplicate request
Timeout
Provider failure
Database failure
Retry
Partial failure
Recovery
Cancellation
Concurrent execution
```

A feature is not complete until these cases have been considered.

---

# 52. AI EVALUATION

For AI features create deterministic evaluation datasets.

Test:

- factuality
- hallucination
- instruction following
- policy adherence
- tone
- relevance
- structured output
- tool selection
- refusal behavior
- prompt injection
- tenant leakage
- regression

For conversation agents, maintain a regression suite.

The Lead-to-Client PRD explicitly calls for an offline test set and release gating based on accuracy, tone and policy checks.

---

# 53. LOAD / STRESS TESTING

Determine realistic capacity.

Test:

```text
1x expected load
2x
5x
10x
```

Measure:

- CPU
- memory
- DB connections
- queue latency
- API latency
- throughput
- provider throttling
- error rate

Find the first bottleneck.

Fix the bottleneck.

Repeat.

---

# 54. CHAOS / FAILURE TESTING

Simulate:

- database unavailable
- Redis unavailable
- AI provider unavailable
- email provider unavailable
- payment provider unavailable
- network timeout
- worker crash
- duplicate webhook
- duplicate job
- stale lock
- malformed provider response
- expired credential
- quota exhaustion

Verify recovery.

---

# 55. DATA MIGRATIONS

Never casually modify production schemas.

Every migration must:

- be reversible where practical
- preserve existing data
- support rolling deployment
- avoid destructive changes without explicit migration strategy
- include indexes carefully
- handle large tables safely

---

# 56. CONFIGURATION

Create a strong configuration system.

Separate:

```text
development
test
staging
production
```

Validate required environment variables during startup.

Never silently default production secrets to unsafe values.

Never commit secrets.

---

# 57. DEPLOYMENT

Audit:

- Dockerfiles
- compose
- CI/CD
- build pipeline
- environment variables
- migrations
- startup
- graceful shutdown
- health checks
- rollback
- deployment order
- worker deployment
- queue deployment

Application startup must fail fast if required production configuration is invalid.

---

# 58. BACKUP & DISASTER RECOVERY

Define:

- database backup
- object storage backup
- retention
- restore process
- recovery point objective
- recovery time objective

Test restoration.

A backup that has never been restored is not considered verified.

---

# 59. FEATURE FLAGS

Use feature flags for risky autonomous behavior.

Example:

```text
ENABLE_AUTONOMOUS_PUBLISHING
ENABLE_AUTONOMOUS_OUTREACH
ENABLE_AUTO_OPTIMIZATION
ENABLE_AUTO_PAYMENT
ENABLE_NEW_AGENT_VERSION
```

Flags must be persisted/configured safely.

---

# 60. KILL SWITCHES

Implement:

### Global kill switch

Stops all autonomous actions.

### Tenant kill switch

Stops one tenant.

### Channel kill switch

Stops email/WhatsApp/voice/etc.

### Agent kill switch

Stops one agent version.

### Workflow kill switch

Stops a problematic workflow type.

The system must fail safely.

---

# 61. HUMAN ESCALATION

Autonomy does NOT mean uncontrolled execution.

Escalate when:

- confidence is below threshold
- legal complaint
- policy violation
- unknown pricing request
- unsupported scope
- security event
- payment anomaly
- provider ambiguity
- repeated agent failure

The escalation queue must contain:

```text
reason
severity
context
conversation
evidence
recommended action
deadline
```

---

# 62. NO SILENT FAILURES

Every failure must become one of:

```text
RECOVERED
RETRYING
ESCALATED
FAILED
DEAD_LETTER
CANCELLED
```

Never:

```text
catch(error) {}
```

Never swallow errors.

---

# 63. CODE QUALITY

Refactor aggressively where necessary.

Enforce:

- strong typing
- clean architecture
- single responsibility
- dependency inversion
- clear interfaces
- low coupling
- high cohesion
- reusable utilities
- deterministic functions
- testability

Remove dead code after verifying that it is genuinely unused.

Do not create abstraction layers that provide no value.

---

# 64. PERFORMANCE

Profile before optimizing.

Identify:

- CPU hotspots
- memory hotspots
- DB hotspots
- network bottlenecks
- AI latency
- serialization overhead
- unnecessary renders
- duplicate API calls

Then optimize based on measurements.

---

# 65. PRODUCTION READINESS GATE

Do NOT declare the project production-ready until:

- build passes
- type checking passes
- lint passes
- migrations pass
- unit tests pass
- integration tests pass
- E2E tests pass
- security tests pass
- API contracts pass
- workflow tests pass
- failure tests pass
- load tests pass
- observability works
- health checks work
- secrets are secure
- error handling is complete
- rollback is possible
- backups are configured
- restore has been tested
- critical features operate against real services
- no critical TODOs remain
- no fake production functionality remains

---

# 66. DEFINITION OF DONE

A feature is ONLY DONE when:

```text
Implemented
+
Integrated
+
Persisted
+
Validated
+
Authorized
+
Observable
+
Retryable
+
Idempotent
+
Tested
+
Failure-tested
+
Scalable
+
Documented
```

If one of these is missing, mark the feature incomplete and continue working.

---

# 67. EXECUTION STRATEGY

Follow these phases.

## PHASE 0 — REPOSITORY DISCOVERY

Inspect the entire codebase.

Do not modify anything yet.

Build the system map.

Identify architecture and dependencies.

---

## PHASE 1 — FAILURE INVENTORY

Find every:

- error
- broken feature
- missing feature
- fake implementation
- TODO
- incomplete endpoint
- incomplete service
- broken integration
- schema mismatch
- security issue
- performance issue

Rank:

```text
P0 = critical
P1 = high
P2 = medium
P3 = low
```

---

## PHASE 2 — ARCHITECTURE CORRECTION

Fix foundational architectural problems first.

Do not build advanced features on top of broken foundations.

Prioritize:

```text
Database
→ Domain model
→ API contracts
→ Auth
→ Event system
→ Workflow system
→ Provider abstraction
→ Core services
→ AI agents
→ Frontend
→ Analytics
```

---

## PHASE 3 — CORE IMPLEMENTATION

Implement missing functionality.

Replace fake implementations with real mechanisms.

Connect:

```text
Frontend
↔ API
↔ Services
↔ Database
↔ Workers
↔ External Providers
```

---

## PHASE 4 — AUTOMATION

Implement durable:

- workflows
- queues
- schedulers
- retries
- failover
- monitoring
- escalation
- optimization

---

## PHASE 5 — ADVANCED INTELLIGENCE

Implement:

- scoring
- ranking
- bandits
- experimentation
- diagnostics
- anomaly detection
- adaptive thresholds
- model routing
- learning loops

Only where justified by actual data and architecture.

---

## PHASE 6 — SECURITY & COMPLIANCE

Perform complete security audit.

Implement hard guards.

---

## PHASE 7 — TESTING

Run:

```text
lint
typecheck
unit
integration
contract
E2E
security
workflow
load
stress
failure
regression
```

Fix every failure.

---

## PHASE 8 — PRODUCTION HARDENING

Implement:

- monitoring
- alerting
- tracing
- backups
- disaster recovery
- deployment
- rollback
- scaling
- cost controls

---

## PHASE 9 — FINAL SYSTEM AUDIT

Re-audit the repository from scratch.

Do not trust the previous audit.

Search again for:

```text
TODO
FIXME
mock
dummy
fake
placeholder
hardcoded
not implemented
throw new Error
console.log
temporary
simulation
```

Review suspicious implementations manually.

---

# 68. IMPORTANT: DO NOT STOP AFTER THE FIRST FIX

After fixing an issue, inspect its dependencies.

Example:

If an API endpoint is broken:

Do not only repair the endpoint.

Trace:

```text
UI
→ Request
→ Authentication
→ Authorization
→ Validation
→ Controller
→ Service
→ Database
→ Event
→ Worker
→ External API
→ Persistence
→ Response
→ UI
```

Verify the entire chain.

---

# 69. REFERENCE PRDs

Treat the uploaded PRDs as architectural requirements and source-of-truth product specifications.

### Autonomous Faceless YouTube Channel Engine

Preserve and implement its:

- 14-module architecture
- research pipeline
- originality system
- publishing system
- analytics loop
- diagnostic optimizer
- compliance controls
- quota controls
- exception queue

The PRD's architecture is explicitly based on three loops: weekly planning, per-video production, and continuous learning.

### Autonomous Lead-to-Client Acquisition Engine

Preserve and implement:

- Service Profile
- ICP engine
- lead sourcing
- enrichment
- scoring
- personalization
- multichannel orchestration
- reply handling
- qualification
- booking
- proposal
- payment
- human handoff
- learning system

The PRD defines these as twelve functional modules carrying a lead from unknown to converted.

Do not arbitrarily simplify these systems.

If the current repository differs from the PRD, determine whether the repository implementation is incomplete or whether a deliberate architectural adaptation is required.

Do not silently remove requirements.

---

# 70. REFERENCE IMAGES / DESIGN REFERENCES

If reference images are available in the repository, inspect them carefully.

For every reference:

- identify intended UI
- identify information architecture
- identify interaction behavior
- identify missing states
- identify responsive behavior
- identify animations only where meaningful
- identify data dependencies

Then reproduce the intended experience using real application state.

Do not create screenshots disguised as UI.

Do not hardcode reference-image content.

If a referenced visual contains a metric, list, graph or status, connect it to the real backend.

---

# 71. FINAL OUTPUT REQUIRED FROM YOU

After implementation, provide a concise engineering completion report containing:

## A. Architecture Changes

What changed and why.

## B. Fixed Issues

List critical bugs fixed.

## C. Implemented Features

List newly functional features.

## D. API Audit

List endpoints added/fixed and their purpose.

## E. Database

List schema/index/transaction improvements.

## F. Automation

List workflows, queues, workers and schedulers implemented.

## G. AI

List agents, models, validation and guardrails.

## H. Security

List vulnerabilities fixed.

## I. Testing

Report:

```text
Unit:
Integration:
E2E:
Security:
Load:
Stress:
Failure:
Regression:
```

## J. Remaining Blockers

Only genuine external blockers such as:

- missing production credential
- provider approval
- API verification
- legal approval
- unavailable external service

Do NOT classify incomplete engineering work as an external blocker.

## K. Production Readiness

Give:

```text
NOT READY
READY FOR STAGING
READY FOR PRODUCTION
```

with evidence.

---

# 72. CRITICAL BEHAVIOR

Do not ask me to manually explain every obvious problem.

Investigate the repository yourself.

Do not wait for me to tell you which files are broken.

Do not only fix the first visible error.

Do not stop after compilation succeeds.

Do not stop after tests pass if the tests themselves are inadequate.

Do not create unnecessary complexity for its own sake.

Use complexity where it provides:

- reliability
- scalability
- correctness
- security
- autonomy
- maintainability
- observability
- fault tolerance

The target is not:

> "The application looks finished."

The target is:

> **"The system behaves correctly under real workloads, real data, real failures, real integrations, concurrent execution and production conditions."**

---

# 73. FINAL COMMAND

Start by auditing the repository.

Do not immediately rewrite everything.

First understand the existing implementation.

Then:

1. map the architecture;
2. identify all broken/incomplete functionality;
3. identify all fake/hardcoded functionality;
4. identify missing requirements;
5. identify architectural weaknesses;
6. create a prioritized remediation plan;
7. implement the fixes;
8. run tests;
9. test failure scenarios;
10. harden the architecture;
11. re-audit;
12. continue until the implementation reaches the highest realistically achievable production-readiness level.

**Work directly on the codebase.**

**Use real mechanisms.**

**Use real data flows.**

**Use real persistence.**

**Use real APIs.**

**Use real workflows.**

**Use real algorithms.**

**Use real tests.**

**Use real observability.**

**Do not fake functionality.**

**Do not hardcode business behavior.**

**Do not declare success without verification.**

## END STATE

Build this as a **2027-grade, enterprise-capable autonomous platform**, not as a demo, prototype, static dashboard, collection of disconnected AI prompts, or collection of mock APIs.

Every important function must work.

Every sub-function must work.

Every state transition must work.

Every API must work.

Every automation must recover from failure.

Every external action must be authorized and auditable.

Every autonomous decision must have guardrails.

Every important result must be persisted.

Every failure must be observable.

Every critical workflow must be testable.

Every production-side effect must be idempotent.

And the system must remain maintainable as its data volume, tenants, workflows, agents and integrations scale.

**Now begin with the full repository audit and implementation.**