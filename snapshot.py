from pathlib import Path
from collectors import *
from collectors.usage import FieldUsageCollector
from config import SNAPSHOT_VERSION,validate_config
from output.json_exporter import export_json
from output.excel_exporter import export_excel
from utils.datetime_utils import iso_timestamp,file_timestamp
from utils.jira_client import JiraClient
from utils.logger import Logger
STANDARD=[("projects",ProjectsCollector),("priorities",PrioritiesCollector),("resolutions",ResolutionsCollector),("issueTypes",IssueTypesCollector),("statuses",StatusesCollector),("customFields",CustomFieldsCollector),("screens",ScreensCollector),("screenSchemes",ScreenSchemesCollector),("issueTypeScreenSchemes",IssueTypeScreenSchemesCollector),("workflows",WorkflowsCollector),("fieldConfigurations",FieldConfigurationsCollector),("projectRoles",ProjectRolesCollector)]
KEYS=["projects","customFields","fieldUsage","screens","screenSchemes","issueTypeScreenSchemes","issueTypes","issueTypeSchemes","statuses","workflows","workflowSchemes","priorities","resolutions","fieldSchemes","fieldConfigurations","fieldConfigurationSchemes","workItemSecuritySchemes","projectRoles","permissionSchemes","notificationSchemes"]
def main():
 validate_config()
 with JiraClient() as c:
  u=c.test_connection();s={"metadata":{"snapshotVersion":SNAPSHOT_VERSION,"created":iso_timestamp(),"site":c.site,"platform":"Jira Cloud","generatedBy":u.get("displayName"),"capabilities":{"fieldSchemesApi":None},"coverage":{}},"statistics":{k:0 for k in KEYS},"data":{k:[] for k in KEYS},"relations":{},"analysis":{}}
  for key,cls in STANDARD:s["data"][key]=cls(c).collect();s["statistics"][key]=len(s["data"][key])
  s["data"]["fieldUsage"]=FieldUsageCollector(c).collect(s["data"]["customFields"]);s["statistics"]["fieldUsage"]=len(s["data"]["fieldUsage"])
  s["metadata"]["coverage"]["customFieldUsage"]=FieldUsageCollector.coverage(s["data"]["fieldUsage"])
  s["metadata"]["coverage"]["workflowScreenReferences"]={"status":"best_effort","source":"workflow search expanded transitions","limitations":["Only screen identifiers exposed by the workflow-search transition payload are included."]}
  s["metadata"]["coverage"]["screenReferences"]={"status":"partial","sources":["screen scheme screens","workflow transition screen identifiers"],"limitations":["Does not prove project usage across team-managed projects, app-managed workflows, drafts, or APIs not visible to this account."]}
  for key,cls,rel in [("workflowSchemes",WorkflowSchemesCollector,"workflowSchemeMappings"),("issueTypeSchemes",IssueTypeSchemesCollector,"issueTypeSchemeMappings"),("fieldConfigurationSchemes",FieldConfigurationSchemesCollector,"fieldConfigurationSchemeMappings"),("workItemSecuritySchemes",WorkItemSecuritySchemesCollector,"workItemSecurityLevels"),("permissionSchemes",PermissionSchemesCollector,"permissionSchemeGrants"),("notificationSchemes",NotificationSchemesCollector,"notificationSchemeEvents")]:s["data"][key],s["relations"][rel]=cls(c).collect();s["statistics"][key]=len(s["data"][key])
  s["data"]["fieldSchemes"],s["metadata"]["capabilities"]["fieldSchemesApi"]=FieldSchemesCollector(c).collect();s["statistics"]["fieldSchemes"]=len(s["data"]["fieldSchemes"])
  p,n,x=GovernanceDependenciesCollector(c).collect(s["data"]["projects"]);s["relations"]["projectPermissionSchemeMappings"]=p;s["relations"]["projectNotificationSchemeMappings"]=n;s["relations"]["projectSecuritySchemeMappings"]=x
 folder=Path(__file__).parent/"snapshots";folder.mkdir(exist_ok=True);stamp=file_timestamp();export_json(s,folder/f"migration_snapshot_{stamp}.json");export_excel(s,folder/f"jira_inventory_{stamp}.xlsx");Logger.info("Snapshot completed successfully")
if __name__=="__main__":main()
