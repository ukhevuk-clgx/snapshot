from concurrent.futures import ThreadPoolExecutor
from collectors.base import BaseCollector
from config import GOVERNANCE_MAX_WORKERS
from utils.logger import Logger
class GovernanceDependenciesCollector(BaseCollector):
 entity_name="governance project dependencies"
 def __init__(self,client,max_workers=GOVERNANCE_MAX_WORKERS):
  super().__init__(client)
  if not isinstance(max_workers,int) or max_workers<1:raise ValueError("max_workers must be a positive integer")
  self.max_workers=max_workers
 def _collect_project(self,p):
  selector=p.get("key") or p.get("id")
  return (
   self.client.get_optional(f"/rest/api/3/project/{selector}/permissionscheme"),
   self.client.get_optional(f"/rest/api/3/project/{selector}/notificationscheme"),
   self.client.get_optional(f"/rest/api/3/project/{selector}/issuesecuritylevelscheme"),
  )
 def collect(self,projects):
  self.start();pm=[];nm=[];sm=[];active=[]
  for p in projects:
   if p.get("archived"):
    Logger.info(f"Skipping governance dependencies for archived project {p.get('key') or p.get('id')}")
    continue
   active.append(p)
  with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
   for idx,(p,(q,n,s)) in enumerate(zip(active,executor.map(self._collect_project,active)),1):
    common={"projectId":p.get("id"),"projectKey":p.get("key"),"projectName":p.get("name"),"projectArchived":p.get("archived")}
    if q:pm.append({**common,"permissionSchemeId":q.get("id"),"permissionSchemeName":q.get("name")})
    if n:nm.append({**common,"notificationSchemeId":n.get("id"),"notificationSchemeName":n.get("name")})
    if s:sm.append({**common,"workItemSecuritySchemeId":s.get("id"),"workItemSecuritySchemeName":s.get("name")})
    if idx%100==0:Logger.info(f"Governance dependencies processed for {idx}/{len(active)} active projects")
  self.done(pm);return pm,nm,sm
