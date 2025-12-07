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

h2. Current Setup

h3. Repository Structure

||Repository||Purpose||Branches||
|*eod-service-mono*|Source code, builds|main|
|*eod-app-deployment*|Helm charts, deployment workflows|sit, uat, prl1, prd|

h3. Current Flow

{panel:title=Current CI/CD Flow|borderStyle=solid|borderColor=#0052CC|bgColor=#f0f5ff}
*eod-service-mono (main branch)*
# Developer merges PR to main
# Builds Docker image
# Deploys to DEV
# Promotes to SIT (auto-push to sit branch in eod-app-deployment)

*eod-app-deployment (sit, uat, prl1, prd branches)*
# sit branch → deploys to SIT environment
# PR: sit → uat → deploys to UAT environment
# PR: uat → prl1 → deploys to PRL1 environment
# PR: prl1 → prd → deploys to PRD environment
{panel}

----

h2. Proposed Solution: Three Pillars

||Pillar||What||Why||
|*1. Multiple Namespaces*|dev1, dev2, uat1, uat2 namespaces|Isolation without infrastructure duplication|
|*2. Override Files*|environments/dev1/values.yaml, environments/uat1/values.yaml, etc.|Environment-specific configuration|
|*3. Feature Flags*|Config-driven flags in Spring Profiles|Control behavior per environment (suppress emails, mock payments, etc.)|

----

h2. Implementation: PR Label Based Deployment

h3. What Changes

||Component||Current||Proposed||
|eod-service-mono (main)|Single DEV deployment|*PR label determines target namespace (dev1 or dev2)*|
|eod-app-deployment (sit)|No change|No change|
|eod-app-deployment (uat)|Single UAT deployment|*PR label determines target namespace (uat1 or uat2)*|
|eod-app-deployment (prl1)|No change|No change|
|eod-app-deployment (prd)|No change|No change|

----

h2. Proposed Flow with PR Labels

{panel:title=Proposed CI/CD Flow|borderStyle=solid|borderColor=#00875A|bgColor=#f0fff5}
*eod-service-mono (main branch)* - WITH PR LABELS FOR DEV
# Developer creates PR to main
# *Developer applies PR label:*
#* {{target:dev1}} → Deploy to dev1 namespace
#* {{target:dev2}} → Deploy to dev2 namespace
#* {{target:all-dev}} → Deploy to both dev1 and dev2
# PR merged to main
# Builds Docker image
# GitHub Actions reads label and deploys to target dev namespace(s)
# Promotes to SIT (auto-push to sit branch)

*eod-app-deployment (sit branch)* - NO CHANGE
# Deploys to SIT environment

*eod-app-deployment (uat branch)* - WITH PR LABELS FOR UAT
# Developer creates PR: sit → uat
# *Developer applies PR label:*
#* {{target:uat1}} → Deploy to uat1 namespace
#* {{target:uat2}} → Deploy to uat2 namespace
#* {{target:all-uat}} → Deploy to both uat1 and uat2
# PR merged
# GitHub Actions reads label and deploys to target uat namespace(s)

*eod-app-deployment (prl1, prd branches)* - NO CHANGE
# PR: uat → prl1 → deploys to PRL1
# PR: prl1 → prd → deploys to PRD
{panel}

----

h2. PR Label Summary

||Repository||Branch||PR Labels||Target Namespaces||
|eod-service-mono|main|{{target:dev1}}, {{target:dev2}}, {{target:all-dev}}|dev1, dev2|
|eod-app-deployment|uat|{{target:uat1}}, {{target:uat2}}, {{target:all-uat}}|uat1, uat2|

----

h2. Visual Flow

{panel:title=Complete PR Label Deployment Flow|borderStyle=solid|borderColor=#ccc|bgColor=#f5f5f5}
{noformat}
eod-service-mono                              eod-app-deployment
----------------                              -------------------

    main                                         sit       uat       prl1      prd
      │                                           │         │          │         │
      │ PR with label                             │         │          │         │
      │ (target:dev1 or                           │         │          │         │
      │  target:dev2 or                           │         │          │         │
      │  target:all-dev)                          │         │          │         │
      │                                           │         │          │         │
      ▼                                           │         │          │         │
 Build Image                                      │         │          │         │
      │                                           │         │          │         │
      ├──────────────┐                            │         │          │         │
      │              │                            │         │          │         │
      ▼              ▼                            │         │          │         │
    dev1           dev2                           │         │          │         │
  namespace      namespace                        │         │          │         │
      │              │                            │         │          │         │
      └──────┬───────┘                            │         │          │         │
             │                                    │         │          │         │
             │ auto-push                          │         │          │         │
             ▼                                    ▼         │          │         │
            SIT ◄─────────────────────────────── sit       │          │         │
                                                  │         │          │         │
                                                  │ PR with │          │         │
                                                  │ label   │          │         │
                                                  │(target: │          │         │
                                                  │ uat1/2) │          │         │
                                                  ▼         ▼          │         │
                                                  └────► uat branch    │         │
                                                           │           │         │
                                                    ┌──────┴──────┐    │         │
                                                    │             │    │         │
                                                    ▼             ▼    │         │
                                                  uat1          uat2   │         │
                                                namespace    namespace │         │
                                                    │             │    │         │
                                                    └──────┬──────┘    │         │
                                                           │           │         │
                                                           │ PR        │         │
                                                           ▼           ▼         │
                                                          prl1 ─────► PRL1       │
                                                           │                     │
                                                           │ PR                  │
                                                           ▼                     ▼
                                                          prd ─────────────────► PRD
{noformat}
{panel}

----

h2. Namespace Structure

||Environment||Namespaces||Purpose||Image Tag||
|DEV|dev1, dev2|Feature development, parallel workstreams|latest|
|SIT|sit|Integration testing|latest|
|UAT|uat1, uat2|uat1: Ongoing testing, uat2: Frozen release candidate|uat1: latest, uat2: locked (v1.2.0)|
|PRL1|prl1|Pre-production|Release version|
|PRD|prd|Production|Release version|

----

h2. Repository Structure

h3. eod-service-mono (main branch)

{code:title=eod-service-mono/|language=none}
eod-service-mono/
├── src/
│   └── main/
│       ├── java/
│       └── resources/
│           ├── application.yml           # Base config
│           ├── application-dev1.yml      # DEV1 feature flags
│           ├── application-dev2.yml      # DEV2 feature flags
│           ├── application-uat1.yml      # UAT1 feature flags
│           └── application-uat2.yml      # UAT2 feature flags
│
└── .github/
    └── workflows/
        └── build-deploy.yml              # PR label based deployment to dev1/dev2
{code}

h3. eod-app-deployment (uat branch)

{code:title=eod-app-deployment/|language=none}
eod-app-deployment/
├── charts/
│   └── eod-service/
│       ├── Chart.yaml
│       ├── values.yaml                   # Base defaults
│       └── templates/
│
├── environments/
│   ├── dev1/
│   │   └── values.yaml                   # DEV1 overrides
│   ├── dev2/
│   │   └── values.yaml                   # DEV2 overrides
│   ├── uat1/
│   │   └── values.yaml                   # UAT1 overrides
│   └── uat2/
│       └── values.yaml                   # UAT2 overrides
│
└── .github/
    └── workflows/
        └── deploy-uat.yml                # PR label based deployment to uat1/uat2
{code}

----

h2. Override Files

h3. environments/dev1/values.yaml

{code:language=yaml}
namespace: dev1

image:
  repository: gcr.io/project/eod-service
  tag: latest

env:
  SPRING_PROFILES_ACTIVE: dev1
  APP_ENVIRONMENT: dev1

ingress:
  host: api-dev1.example.com
{code}

h3. environments/dev2/values.yaml

{code:language=yaml}
namespace: dev2

image:
  repository: gcr.io/project/eod-service
  tag: latest

env:
  SPRING_PROFILES_ACTIVE: dev2
  APP_ENVIRONMENT: dev2

ingress:
  host: api-dev2.example.com
{code}

h3. environments/uat1/values.yaml

{code:language=yaml}
namespace: uat1

image:
  repository: gcr.io/project/eod-service
  tag: latest                          # Always latest

env:
  SPRING_PROFILES_ACTIVE: uat1
  APP_ENVIRONMENT: uat1

ingress:
  host: api-uat1.example.com
{code}

h3. environments/uat2/values.yaml

{code:language=yaml}
namespace: uat2

image:
  repository: gcr.io/project/eod-service
  tag: v1.2.0                          # LOCKED - Release candidate

env:
  SPRING_PROFILES_ACTIVE: uat2
  APP_ENVIRONMENT: uat2

ingress:
  host: api-uat2.example.com
{code}

----

h2. Feature Flags (Spring Profiles)

h3. Feature Flag Summary

||Feature||Config Property||DEV1||DEV2||UAT1||UAT2||PRD||
|Dataflow Template|feature.dataflow.template-version|v2|v2|v2 (new)|v1 (stable)|v1|
|Batch Processing|feature.dataflow.batch-enabled|(/) ON|(/) ON|(/) ON|(x) OFF|(/) ON|
|Email Notifications|integration.email.enabled|(x) OFF|(x) OFF|(x) OFF|(/) ON|(/) ON|
|SMS Alerts|integration.sms.enabled|(x) OFF|(x) OFF|(x) OFF|(x) OFF|(/) ON|
|Payment Gateway|integration.payment.mode|mock|mock|mock|sandbox|real|
|Enhanced Logging|feature.logging.enhanced|(/) ON|(/) ON|(/) ON|(x) OFF|(x) OFF|

----

h2. End-to-End Component Mapping

||Component||DEV1||DEV2||UAT1||UAT2||
|PR Label|target:dev1|target:dev2|target:uat1|target:uat2|
|Repository|eod-service-mono|eod-service-mono|eod-app-deployment|eod-app-deployment|
|Override File|environments/dev1/values.yaml|environments/dev2/values.yaml|environments/uat1/values.yaml|environments/uat2/values.yaml|
|Spring Profile|dev1|dev2|uat1|uat2|
|GKE Namespace|dev1|dev2|uat1|uat2|
|Image Tag|latest|latest|latest|v1.2.0 (locked)|
|Swagger UI|api-dev1.example.com|api-dev2.example.com|api-uat1.example.com|api-uat2.example.com|
|Composer DAG|eod_pipeline_dev1|eod_pipeline_dev2|eod_pipeline_uat1|eod_pipeline_uat2|
|Dataflow Job|eod-dev1-\{ts\}|eod-dev2-\{ts\}|eod-uat1-\{ts\}|eod-uat2-\{ts\}|
|BigQuery Dataset|dataset_dev1|dataset_dev2|dataset_uat1|dataset_uat2|
|GCS Bucket|gs://data-dev1|gs://data-dev2|gs://data-uat1|gs://data-uat2|
|Email|(x) Suppressed|(x) Suppressed|(x) Suppressed|(/) Real|
|Payment|Mock|Mock|Mock|Sandbox|

----

h2. Freeze UAT2 for Release

||Step||Action||
|1|Stop applying {{target:uat2}} label to PRs|
|2|UAT2 image tag remains locked at v1.2.0 in environments/uat2/values.yaml|
|3|Continue using {{target:uat1}} for ongoing development|
|4|(Optional) Pause DAG: {{gcloud composer dags pause eod_pipeline_uat2}}|

----

h2. Adding New Environment (e.g., DEV3 or UAT3)

||Step||Action||Time||Code Change?||
|1|Create application-dev3.yml (or uat3) in eod-service-mono|5 min|(x) No|
|2|Create environments/dev3/values.yaml (or uat3)|5 min|(x) No|
|3|Add label handling to workflow (target:dev3 or target:uat3)|5 min|(x) No|
|4|Create Composer DAG eod_pipeline_dev3 (or uat3)|5 min|(x) No|
|5|Create BigQuery dataset dataset_dev3 (or uat3)|2 min|(x) No|
|6|Create GCS bucket gs://data-dev3 (or uat3)|2 min|(x) No|
|*Total*| |*~25 min*|*Zero code changes*|

----


h2. Logging & Observability

h3. How to Filter Logs by Environment

||Component||Filter Method||Example Query / Filter||
|*GKE Pods*|By namespace|{{resource.labels.namespace_name="uat1"}}|
|*Dataflow Jobs*|By job name prefix or labels|{{resource.labels.job_name=~"eod-uat1-.*"}} or {{labels.env="uat1"}}|
|*Composer DAGs*|By DAG name|{{labels.workflow="eod_pipeline_uat1"}}|
|*BigQuery*|By dataset name|Query {{dataset_uat1.table_name}}|
|*GCS*|By bucket name|{{gs://data-uat1/*}}|
----
h2. Benefits Summary

||Benefit||How It's Achieved||
|Parallel DEV streams|Multiple namespaces (dev1, dev2) via PR labels in eod-service-mono|
|Parallel UAT streams|Multiple namespaces (uat1, uat2) via PR labels in eod-app-deployment|
|Release stability|Locked image tag in uat2, no {{target:uat2}} label|
|Safe testing|Feature flags suppress emails, payments in dev and uat1|
|Low operational overhead|Single cluster, single codebase, config-driven|
|Seamless CI/CD integration|PR labels route deployments (fits existing workflow)|
|Easy "testing" vs "stable"|PR label determines target namespace|
|No code duplication|Same image, different configuration|
|Scalable|Add dev3/uat3 in 25 minutes, zero code changes|

----

h2. What Changes vs Current Setup

||Area||Current||Proposed||Change Impact||
|eod-service-mono (main)|Build → single DEV|Build → PR label selects dev1/dev2|(!) Workflow update|
|eod-app-deployment (sit)|Deploys to SIT|No change|(/) None|
|eod-app-deployment (uat)|Single UAT deployment|PR label selects uat1/uat2|(!) Workflow update|
|eod-app-deployment (prl1/prd)|PR based promotion|No change|(/) None|
|GKE DEV cluster|Single namespace|dev1 + dev2 namespaces|(!) Namespace creation|
|GKE UAT cluster|Single namespace|uat1 + uat2 namespaces|(!) Namespace creation|
|Composer|Single DAG per env|Multiple DAGs (dev1, dev2, uat1, uat2)|(!) DAG creation|
|BigQuery|Single dataset per env|Multiple datasets|(!) Dataset creation|

----

h2. Next Steps

||Phase||Duration||Activities||
|Phase 1|Week 1-2|Create dev1, dev2, uat1, uat2 namespaces; Create override files; Update GitHub Actions workflows in both repos|
|Phase 2|Week 3|Create Spring Profiles (application-dev1.yml, dev2, uat1, uat2); Implement feature flags|
|Phase 3|Week 4|Create Composer DAGs, BigQuery datasets, GCS buckets per namespace|
|Phase 4|Week 5|Migration, validation, team training|

{info:title=Total Implementation Time}
*5 weeks*
{info}
