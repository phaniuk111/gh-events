h1. EOD Multi-Environment Strategy

h2. Parallel UAT Streams with Config-Driven Deployments

----

h2. Problem Statement

* *Environments*: We maintain DEV, SIT, UAT, PRL1 and PROD environments in separate GKE clusters and GCP projects
* *UAT Stability and parallel environments*: Provide ability to support multiple development / UAT streams where:
** We require UAT stability prior to planned production releases
** Allow other longer running UAT use cases to continue which require a regular cadence of releases from DEV into UAT
* *Objective*: Enable safe testing of unstable changes without disrupting the Release

h2. Key Requirements

* Low operational overhead (avoid heavy duplication)
* Seamless integration with existing CI/CD
* Support for shared services
* Easy way to designate deployments as "testing" vs "stable"

h2. Business Impact

||Current State||Impact||
|Single UAT environment|Development blocked during release freeze|
|Release cycle|4-6 weeks (could be 2-3 weeks with parallel streams)|
|Hotfix deployment|Delayed 1-2 weeks waiting for release candidate|
|Environment conflicts|Accidental deployments to release candidate|

----

h2. Proposed Solution: Combined Approach

h3. Three Pillars

||Pillar||What||Why||
|*1. Multiple Namespaces*|uat1, uat2 namespaces in same cluster|Isolation without infrastructure duplication|
|*2. Override Files*|environments/uat1/values.yaml, environments/uat2/values.yaml|Environment-specific configuration|
|*3. Feature Flags*|Config-driven flags in Spring Profiles|Control behavior per environment (suppress emails, mock payments, etc.)|

{panel:title=How They Work Together|borderStyle=solid|borderColor=#ccc|bgColor=#f5f5f5}
*SINGLE CODEBASE* (eod-service)
* One Git branch (uat)
* One Docker image (eod-service:v1.3.0)
* Feature flags embedded in code (read from config)

↓ PR Label determines target ↓

*OVERRIDE FILES* → *FEATURE FLAGS* → *NAMESPACES*

||Component||UAT1 (Ongoing)||UAT2 (Frozen)||
|Override File|environments/uat1/values.yaml|environments/uat2/values.yaml|
|Image Tag|latest|v1.2.0 (locked)|
|Emails|Suppressed|Real|
|Payments|Mock|Sandbox|
|DAG|eod_pipeline_uat1|eod_pipeline_uat2|
{panel}

----

h2. Pillar 1: Multiple Namespaces

h3. What
Deploy the same application to multiple Kubernetes namespaces within the same cluster.

h3. Structure

||Namespace||Purpose||Image Tag||Deployment Frequency||
|dev1|Feature development|latest|Multiple times/day|
|dev2|Parallel feature work|latest|Multiple times/day|
|uat1|Ongoing UAT testing|latest|Daily|
|uat2|Frozen release candidate|v1.2.0 (locked)|Only hotfixes|
|prd|Production|v1.2.0|Scheduled releases|

h3. Isolation Mechanisms

||Mechanism||Purpose||
|Kubernetes Namespace|Logical separation of workloads|
|Network Policies|Block cross-namespace traffic|
|ResourceQuotas|Limit CPU/memory per namespace|
|Separate Ingress|Different URLs (api-uat1.example.com, api-uat2.example.com)|
|RBAC|Namespace-scoped access control|

h3. Benefits
* (/) No additional cluster cost
* (/) Fast to create (5 minutes)
* (/) Complete isolation within same cluster
* (/) Easy to add uat3, uat4

----

h2. Pillar 2: Override Files (Helm Values)

h3. What
Environment-specific configuration files that override default Helm values.

h3. Repository Structure

{code:title=eod-app-deployment/|language=none}
eod-app-deployment/
├── charts/
│   └── eod-service/
│       ├── Chart.yaml
│       ├── values.yaml              # Base defaults
│       └── templates/
│
└── environments/
    ├── dev1/
    │   └── values.yaml              # DEV1 overrides
    ├── dev2/
    │   └── values.yaml              # DEV2 overrides
    ├── uat1/
    │   └── values.yaml              # UAT1 overrides
    ├── uat2/
    │   └── values.yaml              # UAT2 overrides
    └── prd/
        └── values.yaml              # PRD overrides
{code}

h3. Example: environments/uat1/values.yaml (Ongoing Development)

{code:language=yaml}
namespace: uat1

image:
  repository: gcr.io/project/eod-service
  tag: latest                          # Always latest

replicaCount: 2

env:
  SPRING_PROFILES_ACTIVE: uat1
  APP_ENVIRONMENT: uat1

ingress:
  host: api-uat1.example.com
{code}

h3. Example: environments/uat2/values.yaml (Frozen Release)

{code:language=yaml}
namespace: uat2

image:
  repository: gcr.io/project/eod-service
  tag: v1.2.0                          # LOCKED - Release candidate

replicaCount: 2

env:
  SPRING_PROFILES_ACTIVE: uat2
  APP_ENVIRONMENT: uat2

ingress:
  host: api-uat2.example.com
{code}

h3. Benefits
* (/) Git-tracked configuration
* (/) Clear audit trail
* (/) Easy to diff between environments
* (/) No code changes to add new environment

----

h2. Pillar 3: Feature Flags (Config-Driven)

h3. What
Application behavior controlled by configuration properties, NOT hardcoded environment names.

h3. Key Principle: No Environment Names in Code

{code:language=java|title=BAD - Requires code change for every new environment}
if (environment.equals("uat1") || environment.equals("uat2")) {
    mockEmail();
}
{code}

{code:language=java|title=GOOD - Purely config-driven}
if (!featureConfig.getEmail().isEnabled()) {
    log.info("Email suppressed by config");
    return;
}
{code}

h3. Example: application-uat1.yml (Testing Features Enabled)

{code:language=yaml}
feature:
  dataflow:
    template-version: v2               # Test new template
    batch-enabled: true
    batch-size: 1000
  logging:
    enhanced: true                     # Verbose logging

integration:
  email:
    enabled: false                     # Suppress emails
    mock: true
  sms:
    enabled: false                     # Suppress SMS
    mock: true
  payment:
    enabled: true
    mode: mock                         # Mock payments
{code}

h3. Example: application-uat2.yml (Stable Release Candidate)

{code:language=yaml}
feature:
  dataflow:
    template-version: v1               # Stable template
    batch-enabled: false
    batch-size: 100
  logging:
    enhanced: false                    # Standard logging

integration:
  email:
    enabled: true                      # Real emails
    mock: false
  sms:
    enabled: false                     # Still suppress SMS
    mock: true
  payment:
    enabled: true
    mode: sandbox                      # Sandbox payments
{code}

h3. Feature Flag Summary

||Feature||Config Property||UAT1||UAT2||PRD||
|Dataflow Template|feature.dataflow.template-version|v2 (new)|v1 (stable)|v1|
|Batch Processing|feature.dataflow.batch-enabled|(/) ON|(x) OFF|(/) ON|
|Email Notifications|integration.email.enabled|(x) OFF|(/) ON|(/) ON|
|SMS Alerts|integration.sms.enabled|(x) OFF|(x) OFF|(/) ON|
|Payment Gateway|integration.payment.mode|mock|sandbox|real|
|External APIs|integration.external-api.mock|(/) MOCK|(x) REAL|(x) REAL|
|Enhanced Logging|feature.logging.enhanced|(/) ON|(x) OFF|(x) OFF|

h3. Benefits
* (/) Zero code changes to add environment
* (/) Suppress risky integrations in lower environments
* (/) Test new features safely in UAT1
* (/) Git-tracked, auditable

----

h2. How PR Labels Route Deployments

||PR Label||Target Namespace||Override File Used||Spring Profile||
|target:uat1|uat1|environments/uat1/values.yaml|uat1|
|target:uat2|uat2|environments/uat2/values.yaml|uat2|
|target:all-uat|Both uat1 + uat2|Both files|Both profiles|

h3. Deployment Flow

{panel:title=Deployment Flow|borderStyle=solid|borderColor=#0052CC|bgColor=#f0f5ff}
# Developer creates PR: sit → uat
# Adds label: *target:uat1*
# PR Merged
# GitHub Actions checks PR labels
# *target:uat1* found → Deploy to uat1 namespace using environments/uat1/values.yaml with SPRING_PROFILES_ACTIVE=uat1
# *target:uat2* NOT found → Skip uat2 deployment (uat2 remains frozen)
{panel}

----

h2. End-to-End Component Mapping

||Component||UAT1 (Ongoing)||UAT2 (Frozen)||
|PR Label|target:uat1|target:uat2|
|Override File|environments/uat1/values.yaml|environments/uat2/values.yaml|
|Spring Profile|uat1|uat2|
|GKE Namespace|uat1|uat2|
|Image Tag|latest|v1.2.0 (locked)|
|Swagger UI|api-uat1.example.com|api-uat2.example.com|
|Composer DAG|eod_pipeline_uat1|eod_pipeline_uat2|
|Dataflow Job|eod-uat1-\{timestamp\}|eod-uat2-\{timestamp\}|
|BigQuery Dataset|dataset_uat1|dataset_uat2|
|GCS Bucket|gs://data-uat1|gs://data-uat2|
|Email Notifications|(x) Suppressed|(/) Real|
|Payment Gateway|Mock|Sandbox|

----

h2. Adding New Environment (e.g., UAT3)

||Step||Action||Time||Code Change?||
|1|Create application-uat3.yml|5 min|(x) No|
|2|Create environments/uat3/values.yaml|5 min|(x) No|
|3|Create eod_pipeline_uat3 DAG|5 min|(x) No|
|4|Create dataset_uat3 in BigQuery|2 min|(x) No|
|5|Create gs://data-uat3 bucket|2 min|(x) No|
|6|Add target:uat3 label to workflow|5 min|(x) No|
|*Total*| |*~25 min*|*Zero code changes*|

----

h2. Benefits Summary

||Benefit||How It's Achieved||
|Parallel UAT streams|Multiple namespaces (uat1, uat2)|
|Release stability|Locked image tag in uat2 override file|
|Safe testing|Feature flags suppress emails, payments in uat1|
|Low operational overhead|Single cluster, single codebase, config-driven|
|Seamless CI/CD integration|PR labels route deployments|
|Easy "testing" vs "stable"|PR label determines target namespace|
|No code duplication|Same image, different configuration|
|Scalable|Add uat3 in 25 minutes, zero code changes|

----

h2. Comparison with Alternatives

||Approach||Parallel Streams||Operational Overhead||Code Changes for New Env||Cost||
|Multiple Branches|(/)|High (merge conflicts)|Required|Low|
|Separate Repos|(/)|Very High (5x maintenance)|Required|Low|
|Separate Clusters|(/)|High (3x clusters)|Config only|High|
|*Proposed: Namespaces + Overrides + Feature Flags*|(/)|*Low*|*Zero code changes*|*Low*|

----

h2. Next Steps

||Phase||Duration||Activities||
|Phase 1|Week 1-2|Namespace setup (uat1, uat2), Helm override files, ArgoCD config|
|Phase 2|Week 3|GitHub Actions with PR label routing, Feature flag implementation|
|Phase 3|Week 4|Composer DAGs, BigQuery datasets, GCS buckets per environment|
|Phase 4|Week 5|Migration, validation, team training|

{info:title=Total Implementation Time}
*5 weeks*
{info}
