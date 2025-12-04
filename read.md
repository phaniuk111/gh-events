# UAT Multi-Stream Solution

> Options for Supporting Multiple Development/UAT Streams

---

## Problem Statement

| Requirement | Challenge |
|-------------|-----------|
| **UAT Stability** | Need frozen environment before production release |
| **Ongoing UAT** | Regular dev-to-UAT releases must continue |
| **Rapid Hotfix** | Fast path to production for critical fixes |
| **Branch Isolation** | Code branches must not step on each other's toes |

---

## Current State & Pipeline Flow

- **eod-service-mono:** main branch → builds image → deploys to dev
- **eod-app-deployment:** sit, uat, prd branches

**End-to-End Pipeline Flow:**
```
GKE (Spring Boot) → REST API → Composer (DAG) → Dataflow (Flex Template) → BigQuery
```

---

## GKE Setup (Common to All Options)

Both uat1 and uat2 run as separate namespaces in the same GKE cluster, each with its own:

- Spring Boot deployment with environment-specific ConfigMap
- Istio Gateway + VirtualService for separate Swagger UI endpoints
- Service account with Workload Identity for Composer API access

| GKE Component | UAT1 (Ongoing) | UAT2 (Frozen) |
|---------------|----------------|---------------|
| **Namespace** | `uat1` | `uat2` |
| **Spring Boot Image** | `eod-service:v1.3.0` (latest) | `eod-service:v1.2.0` (frozen) |
| **Swagger UI** | `api-uat1.example.com` | `api-uat2.example.com` |
| **Istio Gateway** | `eod-gateway` (in uat1 ns) | `eod-gateway` (in uat2 ns) |
| **ConfigMap** | `ENVIRONMENT=uat1, DAG_ID=...` | `ENVIRONMENT=uat2, DAG_ID=...` |

**Deployment repo structure (uat branch):**
```
├── charts/eod-service/              # Helm templates
├── environments/uat1/values.yaml    # image, dagId, env config
└── environments/uat2/values.yaml    # image, dagId, env config
```

---

## Dataflow Setup (Common to All Options)

Dataflow Flex Template is triggered by Composer DAG. Environment isolation achieved via:

- Job naming convention: `eod-{environment}-{timestamp}`
- Labels for log filtering: `env=uat1` or `env=uat2`
- Separate GCS buckets for temp/staging files
- Output to environment-specific BigQuery datasets

| Dataflow Component | UAT1 (Ongoing) | UAT2 (Frozen) |
|--------------------|----------------|---------------|
| **Flex Template** | `gs://templates/eod-processor` (shared) | `gs://templates/eod-processor` (shared) |
| **Job Name** | `eod-uat1-20241204T120000` | `eod-uat2-20241204T120000` |
| **Labels** | `env=uat1, team=eod` | `env=uat2, team=eod` |
| **Input Bucket** | `gs://data-uat1/input` | `gs://data-uat2/input` |
| **Temp Bucket** | `gs://dataflow-temp-uat1` | `gs://dataflow-temp-uat2` |
| **Output Table** | `project:dataset_uat1.orders` | `project:dataset_uat2.orders` |

**Log Filtering for Dataflow:**
```
# UAT1 logs by job name
resource.type="dataflow_step" AND resource.labels.job_name=~"eod-uat1-.*"

# Or by label
resource.type="dataflow_step" AND labels."env"="uat1"
```

---

## Option 1: Parameterised Single DAG

Spring Boot in each namespace triggers the **SAME DAG** but passes different environment parameter via REST API conf. DAG uses parameter to configure Dataflow job.

### End-to-End Flow

1. uat1 Spring Boot → `POST /dags/eod_pipeline/dagRuns` with `conf: {"environment": "uat1"}`
2. Composer DAG uses `{{ dag_run.conf.environment }}` to set Dataflow params
3. Dataflow job launched as `eod-uat1-{timestamp}` with label `env=uat1`
4. Dataflow writes to `dataset_uat1`

| Component | UAT1 (Ongoing) | UAT2 (Frozen) |
|-----------|----------------|---------------|
| **GKE triggers** | `conf: {env: "uat1"}` | `conf: {env: "uat2"}` |
| **Composer DAG** | `eod_pipeline` (shared) | `eod_pipeline` (shared) |
| **Dataflow Job** | `eod-uat1-{ts}`, labels: `env=uat1` | `eod-uat2-{ts}`, labels: `env=uat2` |
| **BigQuery** | `dataset_uat1` | `dataset_uat2` |

✅ **Pros:** Lowest cost, single DAG to maintain, Dataflow still isolated via naming/labels

❌ **Cons:** Harder to filter Composer logs (must search message content), can't pause one environment, mixed DAG run history

---

## Option 2: Separate DAG Files ⭐ RECOMMENDED

Spring Boot in each namespace triggers its **OWN dedicated DAG**. Each DAG launches its own Dataflow jobs.

### End-to-End Flow

1. uat1 Spring Boot → `POST /dags/eod_pipeline_uat1/dagRuns`
2. `eod_pipeline_uat1` DAG has hardcoded `env="uat1"` for all Dataflow params
3. Dataflow job: `eod-uat1-{timestamp}` → `dataset_uat1`
4. Completely separate run history and logs per DAG

| Component | UAT1 (Ongoing) | UAT2 (Frozen) |
|-----------|----------------|---------------|
| **GKE triggers** | `dagId: eod_pipeline_uat1` | `dagId: eod_pipeline_uat2` |
| **Composer DAG** | `eod_pipeline_uat1` | `eod_pipeline_uat2` |
| **Dataflow Job** | `eod-uat1-{ts}`, labels: `env=uat1` | `eod-uat2-{ts}`, labels: `env=uat2` |
| **BigQuery** | `dataset_uat1` | `dataset_uat2` |

✅ **Pros:** Clear Airflow UI separation, easy log filtering, can pause uat2 DAG (stops Dataflow triggers), separate run history

❌ **Cons:** DAG code duplication (mitigated with factory pattern)

### Freeze UAT2

1. Lock `uat2/values.yaml` image tag
2. Pause DAG: `gcloud composer dags pause eod_pipeline_uat2` → No more Dataflow jobs for uat2

### DAG Factory Pattern

```python
# dags/eod_pipeline_factory.py
from airflow import DAG
from airflow.providers.google.cloud.operators.dataflow import DataflowStartFlexTemplateOperator
from datetime import datetime

def create_eod_dag(env: str) -> DAG:
    with DAG(
        dag_id=f"eod_pipeline_{env}",
        schedule_interval=None,
        start_date=datetime(2024, 1, 1),
        catchup=False,
        tags=[env, "eod", "dataflow"]
    ) as dag:

        process_data = DataflowStartFlexTemplateOperator(
            task_id="process_data",
            project_id="your-project",
            location="europe-west2",
            body={
                "launchParameter": {
                    "jobName": f"eod-{env}-{{{{ ts_nodash }}}}",
                    "containerSpecGcsPath": "gs://your-bucket/templates/eod-processor",
                    "parameters": {
                        "environment": env,
                        "inputBucket": f"gs://data-{env}",
                        "outputTable": f"project:dataset_{env}.orders"
                    },
                    "environment": {
                        "additionalUserLabels": {"env": env}
                    }
                }
            }
        )

    return dag

# Generate DAGs
eod_pipeline_uat1 = create_eod_dag("uat1")
eod_pipeline_uat2 = create_eod_dag("uat2")
```

### Log Filtering

```
# Composer logs - filter by workflow name directly
resource.type="cloud_composer_environment"
labels."workflow"="eod_pipeline_uat1"

# Dataflow logs
resource.type="dataflow_step"
resource.labels.job_name=~"eod-uat1-.*"
```

---

## Option 3: Separate Composer Environments

Each GKE namespace triggers its own Composer environment. Maximum isolation for both DAGs and Dataflow.

### End-to-End Flow

1. uat1 Spring Boot → `composer-uat1` Airflow API
2. composer-uat1 DAG → launches Dataflow `eod-uat1-{timestamp}`
3. Completely separate Composer UIs, logs, and Dataflow jobs

| Component | UAT1 (Ongoing) | UAT2 (Frozen) |
|-----------|----------------|---------------|
| **GKE triggers** | `composer-uat1` API | `composer-uat2` API |
| **Composer** | `composer-uat1` (separate) | `composer-uat2` (separate) |
| **Dataflow Job** | `eod-uat1-{ts}` | `eod-uat2-{ts}` |
| **BigQuery** | `dataset_uat1` | `dataset_uat2` |

✅ **Pros:** Full isolation, can test Composer upgrades in uat1, uat2 completely frozen

❌ **Cons:** 2x Composer cost (~$300-500/month each), more infrastructure, separate Airflow URLs

---

## Option 4: Single DAG + BigQuery Views

Both GKE namespaces trigger same DAG, Dataflow writes to same table with env column. Data isolation via BigQuery views only.

### End-to-End Flow

1. Both uat1/uat2 → same DAG with env parameter
2. Dataflow writes to same table: `dataset_uat.orders` with `env` column
3. Views filter: `SELECT * FROM orders WHERE env='uat1'`

| Component | UAT1 (Ongoing) | UAT2 (Frozen) |
|-----------|----------------|---------------|
| **GKE triggers** | `eod_pipeline (env=uat1)` | `eod_pipeline (env=uat2)` |
| **Dataflow Output** | `dataset_uat.orders (env=uat1)` | `dataset_uat.orders (env=uat2)` |
| **BigQuery Access** | `orders_uat1` (VIEW) | `orders_uat2` (VIEW) |

✅ **Pros:** Simplest infrastructure, single pipeline

❌ **Cons:** Data mixed in same table, no DAG-level freeze, Dataflow jobs still mixed, harder to delete env data

---

## Options Comparison Matrix

| Aspect | Option 1 | Option 2 ⭐ | Option 3 | Option 4 |
|--------|----------|-------------|----------|----------|
| **GKE** | 2 namespaces | 2 namespaces | 2 namespaces | 2 namespaces |
| **Composer** | 1, params | **1, 2 DAGs** | 2 separate | 1, params |
| **Dataflow** | ✅ Separate jobs | ✅ Separate jobs | ✅ Separate jobs | ⚠️ Mixed jobs |
| **BigQuery** | ✅ 2 datasets | ✅ 2 datasets | ✅ 2 datasets | ⚠️ 1 + views |
| **Cost** | 💚 $ | 💚 $ | 🔴 $$$ | 💚 $ |
| **Freeze UAT2** | ⚠️ Lock image | ✅ Pause DAG | ✅ Freeze env | 🔴 No control |
| **Log Filtering** | ⚠️ Search msg | ✅ By workflow | ✅ By env | ⚠️ Search msg |
| **Run History** | ⚠️ Mixed | ✅ Separate | ✅ Separate | ⚠️ Mixed |

---

## Answer: Do We Need Another SIT Environment?

> **No.**
> 
> Add GKE namespaces + DAG files + BigQuery datasets + GCS buckets. No new Composer environment needed. Dataflow uses same Flex Template with different parameters.

---

## Recommendation Summary

> ### ⭐ Option 2: Separate DAG Files
> 
> Best balance of isolation, observability, and cost.
> 
> **Flow:** GKE → separate DAGs → separate Dataflow jobs → separate BigQuery datasets

**Hotfix Path:** Use existing SIT branch → PRD (bypasses UAT entirely)

---

## Implementation Checklist

### GKE
- [ ] Create `uat1` namespace
- [ ] Create `uat2` namespace
- [ ] Deploy Spring Boot with environment-specific ConfigMap
- [ ] Configure Istio Gateway per namespace
- [ ] Update `eod-app-deployment` repo with `environments/uat1/values.yaml` and `environments/uat2/values.yaml`

### Composer
- [ ] Create `eod_pipeline_uat1` DAG
- [ ] Create `eod_pipeline_uat2` DAG
- [ ] Or use factory pattern to generate both

### Dataflow
- [ ] No new Flex Template needed (shared)
- [ ] Ensure job naming includes environment: `eod-{env}-{timestamp}`
- [ ] Add labels: `env=uat1`, `env=uat2`

### BigQuery
- [ ] Create `dataset_uat1`
- [ ] Create `dataset_uat2`

### GCS
- [ ] Create `gs://data-uat1` bucket
- [ ] Create `gs://data-uat2` bucket
- [ ] Create `gs://dataflow-temp-uat1` bucket
- [ ] Create `gs://dataflow-temp-uat2` bucket

---

## Future Enhancement: Pub/Sub Trigger

If migrating from REST API to Pub/Sub:

```
┌─────────────────┐     ┌─────────────────┐
│     uat1        │     │     uat2        │
│  Spring Boot    │     │  Spring Boot    │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│ eod-trigger-uat1│     │ eod-trigger-uat2│
│ (Pub/Sub Topic) │     │ (Pub/Sub Topic) │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│eod_pipeline_uat1│     │eod_pipeline_uat2│
│(DAG with sensor)│     │(DAG with sensor)│
└─────────────────┘     └─────────────────┘
```

Separate topics per environment for clean isolation.
