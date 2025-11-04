| Capability | Terraform Support | Type / Scope | Metric-Based | Log-Based | SLO-Based | Prometheus | Description |
|-------------|------------------|---------------|---------------|------------|------------|-------------|--------------|
| notification_rate_limit | Yes (as argument) | API (Policy Config) | No effect | Required | No effect | No effect | Sets min. time between notifications for a single log incident. |
| auto_close | Yes (as argument) | API (Policy Config) | Yes | Yes | Yes | Yes | Auto-closes an open incident if no new data arrives for the set duration. |
| notification_prompts | Yes (as argument) | API (Policy Config) | Yes | OPENED only | Yes | Yes | Defines when to notify, e.g., [OPENED, CLOSED]. |
| "Acknowledge" (UI) | No (UI Action) | UI-Only (Informational) | Yes | Yes | Yes | Yes | UI-only state change. Signals a team member is investigating. Does not stop notifications. |
| "Close Incident" (UI) | No (UI Action) | UI-Only (Incident Action) | Yes | Yes | Yes | Yes | Manually closes an incident. A new incident will be created if the condition is still true. |
| "Snooze" (Policy-Level) | No Resource | API-Backed (Functional Mute) | Yes | Yes | Yes | Yes | True Mute. Creates an API "Snooze" object to prevent all new incidents & notifications for a set time. |
| Disable Policy | Yes (as argument) | API-Backed (Policy Config) | Yes | Yes | Yes | Yes | Sets the policy's enabled = false state. Stops all evaluations. |
| Stop notifications after "Acknowledge" | No (Not a feature) | Not Supported | No | No | No | No | The ability to "ack" an incident to silence it. |
| Escalation Policies | No (Not a feature) | Not Supported | No | No | No | No | Multi-step notifications (e.g., PagerDuty). |
| Integration (Pub/Sub, etc.) | Yes (as argument) | API (Policy Config) | Yes | Yes | Yes | Yes | Send alert JSON to an external system for handling. |
