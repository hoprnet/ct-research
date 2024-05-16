# ctdApp Deployment docs


## Connect to Database

```bash
gcloud compute instances start --project=hopr-prod --zone=europe-west3-a bastion
gcloud compute ssh bastion --zone=europe-west3-a --project=hopr-prod -- -L 5432:localhost:5432
export PGHOST=localhost
export PGPORT=5432
export PGDATABASE=ctdapp
export PGUSER=ctdapp
export PGPASSWORD=`Get from Bitwarden secret "ctdApp - Postgres Production"`
psql
```
