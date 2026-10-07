from collectors.base import BaseCollector
class IssueTypeSchemesCollector(BaseCollector):
 entity_name="issue type schemes"
 def collect(self):
  self.start();raw=self.client.get_paginated("/rest/api/3/issuetypescheme",params={"orderBy":"name","expand":"projects"});schemes=[{"id":x.get("id"),"name":x.get("name"),"description":x.get("description"),"defaultIssueTypeId":x.get("defaultIssueTypeId"),"isDefault":x.get("isDefault"),"projectCount":(x.get("projects") or {}).get("total")} for x in raw];maps=[]
  for x in self.client.get_paginated("/rest/api/3/issuetypescheme/mapping"):
   ids=x.get("issueTypeIds") or ([x.get("issueTypeId")] if x.get("issueTypeId") is not None else []);maps += [{"issueTypeSchemeId":x.get("issueTypeSchemeId"),"issueTypeId":str(i)} for i in ids]
  self.done(schemes);return schemes,maps
