from collectors.base import BaseCollector
class WorkItemSecuritySchemesCollector(BaseCollector):
 entity_name="work item security schemes"
 def collect(self):
  self.start();payload=self.client.get("/rest/api/3/issuesecurityschemes") or {};schemes=[];levels=[]
  for x in payload.get("issueSecuritySchemes",[]):
   ls=(self.client.get(f"/rest/api/3/issuesecurityschemes/{x.get('id')}") or {}).get("levels",[]);schemes.append({"id":x.get("id"),"name":x.get("name"),"description":x.get("description"),"defaultSecurityLevelId":x.get("defaultSecurityLevelId"),"securityLevelCount":len(ls),"apiResource":"issue security schemes"});levels += [{"schemeId":x.get("id"),"levelId":l.get("id"),"name":l.get("name"),"description":l.get("description"),"isDefault":str(l.get("id"))==str(x.get("defaultSecurityLevelId"))} for l in ls]
  self.done(schemes);return schemes,levels
