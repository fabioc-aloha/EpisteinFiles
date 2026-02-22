# Azure Portal Setup — pgvector Extension

## What's Already Provisioned

| Resource | Name | Region | Status |
|----------|------|--------|--------|
| Resource Group | `rg-epstein-files` | East US | ✅ Ready |
| Log Analytics | `log-epstein-files` | East US | ✅ Ready |
| Container Apps Environment | `cae-epstein-files` | East US | ✅ Ready |
| Cosmos DB for PostgreSQL | `psql-epstein-files` | East US | ✅ Ready (needs pgvector) |

## Manual Step: Enable pgvector Extension

1. Open [Azure Portal](https://portal.azure.com)
2. Search for **`psql-epstein-files`** in the top search bar
3. Open the **Azure Cosmos DB for PostgreSQL Cluster**
4. In the left sidebar, go to **Settings → Server parameters**
5. In the **search/filter box**, type `azure.extensions`
6. Click the `azure.extensions` parameter row
7. From the dropdown list, **check the box next to `VECTOR`**
8. Click **Save** at the top of the page
9. Wait for the save to complete (~1-2 minutes, may require a restart)

## Connection Details

| Property | Value |
|----------|-------|
| Host | `c-psql-epstein-files.lskbn4jtyil425.postgres.cosmos.azure.com` |
| Port | `5432` |
| Database | `citus` |
| User | `citus` |
| Password | `Epst3in!F1les2026#` |
| SSL | Required |

## What Happens Next

Once pgvector is allowlisted, run this to apply the database schema:

```powershell
cd c:\Users\fabioc\EpisteinFiles
python -c "
import psycopg2
conn = psycopg2.connect(
    host='c-psql-epstein-files.lskbn4jtyil425.postgres.cosmos.azure.com',
    port=5432, dbname='citus', user='citus',
    password='Epst3in!F1les2026#', sslmode='require'
)
conn.autocommit = True
cur = conn.cursor()
with open('db/init.sql', 'r') as f:
    cur.execute(f.read())
cur.execute('SELECT tablename FROM pg_tables WHERE schemaname = ''public''')
print('Tables:', [t[0] for t in cur.fetchall()])
cur.close(); conn.close()
"
```

## Remaining Infrastructure (to do next session)

- [ ] Apply database schema (after pgvector is enabled)
- [ ] Update `.env` with connection strings
- [ ] Update code to remove Blob Storage references (architecture pivot: files stay on government servers)
- [ ] Build and deploy Container App (web + worker)
- [ ] Configure custom domain (correax.com)

## Firewall Note

⚠️ The firewall currently allows all IPs (`0.0.0.0 - 255.255.255.255`). After setup is complete, restrict to:
- Azure services only (`0.0.0.0 - 0.0.0.0`)
- Your specific IP address
