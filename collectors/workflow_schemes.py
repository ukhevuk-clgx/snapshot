from collectors.base import BaseCollector
class WorkflowSchemesCollector(BaseCollector):
 entity_name="workflow schemes"
 def collect(self):
  self.start();raw=self.client.get_paginated("/rest/api/3/workflowscheme");schemes=[];maps=[]
  for x in raw:
   m=x.get("issueTypeMappings") or {};schemes.append({"id":x.get("id"),"name":x.get("name"),"description":x.get("description"),"defaultWorkflow":x.get("defaultWorkflow"),"issueTypeMappingCount":len(m)})
   if x.get("defaultWorkflow"):maps.append({"workflowSchemeId":x.get("id"),"issueTypeId":None,"workflowName":x.get("defaultWorkflow"),"isDefault":True})
   maps += [{"workflowSchemeId":x.get("id"),"issueTypeId":str(k),"workflowName":v,"isDefault":False} for k,v in m.items()]
  self.done(schemes);return schemes,maps
