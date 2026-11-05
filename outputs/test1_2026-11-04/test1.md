### Public Blob Enumeration Enabled on Azure Storage Container (db-backups)

CVSS: CVSS:5.3/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N

Status: Not Remediated

Affected Endpoints:
- https://koilidpsprodstorage.blob.core.windows.net/db-backups/

Description:

Public blob enumeration vulnerabilities occur when an Azure Storage container allows unauthenticated users to list blob names, metadata, or properties. Even if the storage container does not permit downloading the actual blob content, exposing blob metadata can leak sensitive information such as file names, timestamps, internal naming conventions, and operational details.

In the assessed Azure environment, the storage container “db-backups” was found to allow public enumeration of blobs. Anyone with the container URL can list blob names and their metadata without authentication. Although the blob content was not exposed, this misconfiguration increases reconnaissance capability for attackers and may lead to future data exposure if real backups are uploaded without correcting permissions.

Recommendation:

Disable all public access to the Azure Storage account and set the container access level to Private.
Allow blob access only through Azure AD, SAS tokens, or Managed Identity with strict permissions.

Impact:

An attacker can exploit this vulnerability to:
Enumerate blob names, timestamps, sizes, and metadata without authentication.
Obtain internal naming patterns, backup schedules, and file structure.
Perform targeted phishing or social-engineering attacks based on discovered filenames.
- Gain insight for future attacks (e.g., backup tampering if permissions change).

Although the content itself is not downloadable, metadata exposure qualifies as an information disclosure risk.

Steps For Reproduction:

Visit: https://koilidpsprodstorage.blob.core.windows.net/db-
backups?restype=container&comp=liston yourbrowser.
Observe that blob names and metadata are publicly visible without authentication.
Confirm that the container is misconfigured by verifyingthe XML output displays blob listings.

### Publicly Accessible Azure Service Bus

CVSS: CVSS:5.3/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N

Status: Not Remediated

Affected Endpoints:
- https://koili-dev.servicebus.windows.net/
- https://koili-staging.servicebus.windows.net/
- https://koili-prod.servicebus.windows.net/

Description:

Azure Service Bus namespaces should be protected behind network restrictions
(Private Endpoints, VNet integration, IP firewall rules). When a namespace is left
publicly reachable, anyone on the internet can directly query Service Bus
management endpoints.

During assessment, the Service Bus namespace koili-dev/koili-staging/koili-prod responded 200 (ok) to multiple unauthenticated requests sent to its
management endpoints:

$namespaceinfo
$Resources/Queues
$Resources/Topics
$Resources/Subscriptions

Although the namespace currently contains no active queues/topics, the
namespace itself is exposed and queryable. This increases attack surface and
enables reconnaissance on internal resources.

Recommendation:

Disable all public access to the Azure Service Bus.
Enforce strict authentication using:
Azure AD
SAS tokens
Managed Identity

Reference:
- https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-
- bus-ip-filtering

Impact:

A publicly reachable Service Bus namespace allows an attacker to:
Discover and enumerate the namespace using unauthenticated requests. Probe internal management endpoints, confirming service status and structure.
Fingerprint the environment (API version, service type, XML formats, server behavior).
Prepare for future exploitation if queues/topics get created later with weak permissions.

Steps For Reproduction:

Run a public-network scan to check reachability: nmap -Pn -p 567l koili- (dev|staginglprod).servicebus.windows.net
Observe that port 5671 (AMQP over TLS)is open and responsive from the internet.
Verify a successful TLS handshake to the AMQP endpoint: openssl s_client – connect koili-(dev|staginglprod).servicebus.windows.net:5671.
Confirm that no firewall, Private Endpoint, or IP restriction blocks anonymous network access.

### Azure SQL Database Publicly Reachable Over the Internet

CVSS: CVSS:5.3/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N

Status: Not Remediated

Affected Endpoints:
- koili-db-prod.database.windows.net
- koili-db-dev.database.windows.net

Description:

Azure SQL Databases should be protected behind network restrictions such as Private Endpoints, VNet integration, and IP firewall rules. When a SQL Database is publicly reachable, anyone on the internet can connect to the SQL endpoint and attempt network-level authentication, enabling password-guessing attacks, credential-stuffing attempts, and broad reconnaissance of the database service.

During the assessment, the SQL Database servers koili-db-prod and koili-db-dev were found to be publicly reachable over port 1433 (MS SQL Server) from any external network. No firewall, IP restriction, or network control was in place to prevent unauthenticated access attempts.

Although valid credentials are still required to access the databases, this exposure significantly increases the attack surface by allowing attackers to perform reconnaissance, brute-force login attempts, and misuse leaked or weak passwords.

Recommendation:

Disable public network access entirely for all Azure SQL Databases.

Reference:
- https://learn.microsoft.com/en-us/azure/azure-sql/database/network-
- access-controls-overview?view=azuresql

Impact:

A publicly reachable Azure SQL Database allows an attacker to:
Identify SQL Server endpoints, confirming SQL services are running.
Perform large-scale password brute-force or credential-stuffing attacks.
Probe TLS handshake and gather server version metadata.
Enumerate timing responses to guess authentication behavior.
Prepare for exploitation if weak SQL credentials or outdated configurations exist.
Use the information for targeted attacks against the organization's cloud assets.

Steps For Reproduction:

Test public reachability of the SQL endpoint:
onc -vz koili-db-prod.database.windows.net 1433
onc -vz koili-db-dev.database.windows.net1433

- Verify that the SQL server accepts TLS connections:
O
openssl s_client -connect koili-db-
prod.database.windows.net:1433
O
openssl s_client -connect koili-db-
dev.database.windows.net:1433

Confirm that no firewall, Private Endpoint, or IP restriction blocks anonymous access from the internet.

### Public Network Access Enabled for Azure Key Vault

CVSS: CVSS:5.3/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N

Status: Not Remediated

Affected Endpoints:
- koili-keyvault-prod.vault.azure.net

Description:

Azure Key Vaults should be isolated from the public internet. If a Key Vault is reachable publicly, it allows anyone on the internet to attempt connections to the vault endpoint, potentially enabling reconnaissance, token-guessing, or brute- force attacks.

During the assessment, the Key Vault koili-keyvault-prod was found to be accessible over the internet at: https://koili-keyvault-prod.vault.azure.net/

No network restrictions were configured to prevent unauthenticated access attempts. While authentication is still required to read secrets or keys, the public exposure increases the risk of targeted attacks or future misconfigurations being exploited.

Recommendation:

Disable public network access for the Key Vault.
Apply firewall rules for limited, controlled access for required networks and applications.

Reference:
- https://learn.microsoft.com/en-us/azure/key-vault/general/network-
- security

Impact:

A Key Vault that is reachable publicly can allow an attacker to:

Discover vault endpoints and confirm the Key Vault service is active.
Attempt brute-force attacks on tokens or credentials.
Prepare targeted attacks if vault permissions or secrets are mismanaged.

Steps For Reproduction:

Check if the Key Vault endpoint is reachable over the internet:
ocurl-ihttps://koili-keyvault-prod.vault.azure.net/secrets?api-
version=7.3
Observe the response to confirm authentication is required.
