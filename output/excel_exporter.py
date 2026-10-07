from pathlib import Path
import pandas as pd
SHEETS=[("Projects","projects"),("Custom Fields","customFields"),("Screens","screens"),("Screen Schemes","screenSchemes"),("Issue Type Screen Schemes","issueTypeScreenSchemes"),("Issue Types","issueTypes"),("Issue Type Schemes","issueTypeSchemes"),("Statuses","statuses"),("Workflows","workflows"),("Workflow Schemes","workflowSchemes"),("Priorities","priorities"),("Resolutions","resolutions"),("Field Schemes","fieldSchemes"),("Field Configurations","fieldConfigurations"),("Field Configuration Schemes","fieldConfigurationSchemes"),("Work Item Security Schemes","workItemSecuritySchemes"),("Project Roles","projectRoles"),("Permission Schemes","permissionSchemes"),("Notification Schemes","notificationSchemes")]
REL=[("Workflow Scheme Mappings","workflowSchemeMappings"),("Issue Type Scheme Mappings","issueTypeSchemeMappings"),("Field Config Scheme Mappings","fieldConfigurationSchemeMappings"),("Work Item Security Levels","workItemSecurityLevels"),("Permission Scheme Grants","permissionSchemeGrants"),("Notification Scheme Events","notificationSchemeEvents"),("Project Permission Schemes","projectPermissionSchemeMappings"),("Project Notification Schemes","projectNotificationSchemeMappings"),("Project Security Schemes","projectSecuritySchemeMappings")]
def write(w,rows,name):
 df=pd.DataFrame(rows or [{"Message":"No data returned"}]);safe=name[:31];df.to_excel(w,sheet_name=safe,index=False);ws=w.sheets[safe];ws.freeze_panes(1,0);ws.autofilter(0,0,max(len(df),1),len(df.columns)-1)
def export_excel(s,path):
 meta=[{"Section":"Metadata","Property":k,"Value":v} for k,v in s["metadata"].items() if k!="capabilities"]+[{"Section":"Capability","Property":k,"Value":v} for k,v in s["metadata"].get("capabilities",{}).items()]+[{"Section":"Statistics","Property":k,"Value":v} for k,v in s["statistics"].items()]
 with pd.ExcelWriter(Path(path),engine="xlsxwriter") as w:
  write(w,meta,"Summary")
  for name,key in SHEETS:write(w,s["data"].get(key,[]),name)
  if "fieldUsage" in s["data"]:write(w,s["data"]["fieldUsage"],"Custom Field Usage")
  if s["metadata"].get("coverage"):write(w,[{"Area":key,"Coverage":value} for key,value in s["metadata"]["coverage"].items()],"Usage Coverage")
  for name,key in REL:write(w,s["relations"].get(key,[]),name)
