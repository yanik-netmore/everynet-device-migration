# Everynet migration

Tool to migrate easily devices from Everynet LNS to TPE.

# Configuration

See in **migration.sample.json**:

```
{
  "fqdn": "ns.eu.everynet.io",
  "username": "EMAIL",
  "password": "PASSWORD",
  "suspend_list": "deveuis-list.csv",
  "suspend_retries": 3,
  "suspend_progress": "patch_progress.txt",
  "url": "https://ns.eu.everynet.io/api/v1.0/devices",
  "limit": 100,
  "outputdir": "subdirectory",
  "orgs": [
    {"orgID": "665705abc2e7xxxxxxxxxxxx", "name": "First_ORG", "keyID": "6a1e95ab2cb898xxxxxxxx", "apiToken": "xxxxxx"},
    {"orgID": "642566a60675xxxxxxxxxxxx", "name": "Second_ORG", "keyID": "6a1e9532906bfxxxxxxxzx", "apiToken": "yyyy"}
  ]
}
```


# Prerequisite
- Gather the organizationIDs you want to migrate, i.e.: 665705abc2e7xxxxxxxxxxxx
- Create API keys and token for each organizationID
- Create all the data connections beforehand
- Gather tuple DevEUI,ConnectionID (The most complicated to get)

## OrganizationsID and Keys
- Check in https://ns.eu.everynet.io/organizations for Everynet EU platform
- OR- use this help script to pull all organizationIDs:

```
python3 get-organizations.py -c migration.sample.json --output-dir org
```
- Search for organisameName and write down its organisationID:

```
$ python3 get-organizationID.py -i org/organizations.json --org "iot ras"
5d2eee4acc613a00014b9c49	IoT RAS
```

- For each organizationID create a key in https://ns.eu.everynet.io/keys
  - Details:
    - User: Administrator
    - Organisation ID: Unfortunately no search possible, and no sorting possible, scroll until you find the organisationName
      - Double check if the ID displayed match the ID of the previous step
    - Description: set something meaningful like "Migration: CUSTOMER orgName"
    - For All **Permissions** choose **ALL**
    - Click save
    - Copy the **Key ID** and **Access token** to thew configuration file
    

# Migration


- Create the mass import file:
  - e.g with connectivity plan named **actility-tpe-cs/tpe-cp-pr** and Connection ASID named **TUTU**
    - All the results with be in **config["outputdir"]**
      - all.import.csv: To import in TPW impersonating the Subscriber
      - all.delete.csv: To mass delete if needed
      - deveui-list.csv: list of DevEUI with exported context (for next steps)

```
python3 extract-everynet-devices-info.py -c migration.sample.json --cp actility-tpe-cs/tpe-cp-pr --as TUTU
```

**Note:** If existing, Device's lat,lon are populated in **all.import.csv**

- To be on the safe side make a copy of **all.import.csv** first

```
cp all.import.csv all.import.csv.org
```
- Update the all.import.csv so the **TUTU** ASID becomes ASID from tuple DevEUI,ConnectionID
  - This is not automated yet
  - Can be time consuming to do on bigger batch


- in TPW after impersonate the destination subscriber, open **Things Manager** tab
- Choose **Devices** then **Bulk Operations**
- Click on the *paperclip icon* and Browse to your **all.import.csv**
  
  
  
 
