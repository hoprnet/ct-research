# Manually update node on GCP

In case of a necessary manual update of the node hosted on GCP, here's some default step to modify its configuration.
Everything is to be done from the command line.

### Node list

Here are the remaining nodes hosted on GCP:
- ctdapp-production-1
- ctdapp-production-2
- ctdapp-production-3
- ctdapp-production-4
- ctdapp-production-5

### SSH to the node

Using `gcloud` command (install [link](https://cloud.google.com/sdk/docs/install-sdk)), SSH to the desired node:

```bash
gcloud compute ssh <instance>
```

### Run as root

```bash
sudo su
```

### Move to the node's directory

```bash
cd /opt/hoprd
```

### Stop node

```bash
service hoprd stop
```

### Do a backup of the node

```bash
mv db db_backup
mv tbf tbf_backup
```

### Modify the files

To update the node's version, modify the `.env` file:
```bash
nano .env
```
and set the variable `HOPRD_VERSION` to any desired version.

To set a different RCP provider, modify the `.env-hoprd` file:
```bash
nano .env-hoprd
```

modify (or add) the following line:
```bash
HOPRD_PROVIDER=<rpc-url>
```

or modify any desired parameter in any of the `.env`, `.env-default` or `.env-hoprd` files.

### Restart the node

```bash
service hoprd restart
```

And then check the syncing progress my looking at the docker container logs

```bash
docker logs -t hoprd
```