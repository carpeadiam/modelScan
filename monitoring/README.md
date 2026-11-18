# Monitoring

The dashboard's **Monitoring** page queries real Cloud Monitoring (`run.googleapis.com/request_count`,
`request_latencies`, `container/memory/utilizations`) and Cloud Logging (error entries for the Cloud Run service
and Cloud Build). Build failures themselves come from the Cloud Build API records.

Optional alert (needs a notification channel; alerting policies beyond free allotments can cost money):

    gcloud alpha monitoring policies create --policy-from-file=monitoring/alert_policy_5xx.json

Add `--notification-channels=CHANNEL_ID` after creating a channel in the console.
